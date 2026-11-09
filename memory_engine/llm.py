"""Cohere helpers: extraction, conflict judging, embeddings, answering."""
from __future__ import annotations

import json
import os
import re
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

CHAT_MODEL = os.getenv("COHERE_CHAT_MODEL", "command-a-03-2025")
EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0")
EMBED_BATCH = 96  # Cohere accepts at most 96 texts per embed call

EXTRACT_PROMPT = """You extract durable facts from a conversation or document so an AI assistant can remember them later.

Rules:
- Output atomic facts: one claim per fact, written as a complete, self-contained sentence. Resolve pronouns ("she" -> the person's name) so the fact makes sense without the original text.
- Every fact must name the person, team or project it is about (e.g. "Meera uses Microsoft Teams for team communication." — not "The communication tool is Microsoft Teams."). Never write a fact that only makes sense if you know who was talking.
- Keep facts about people, projects, decisions, owners, dates, deadlines, preferences, tools and status changes.
- When something CHANGED or was REPLACED (e.g. "The billing migration's payment provider is Razorpay."), always output a separate fact stating the new current value of that attribute (e.g. "The payment provider is Razorpay."). Do not mention the old value in that fact, and never write "moved from X to Y".
- Reasons and explanations ("because of lower fees") may be their own fact, but must never replace the fact stating the new value.
- Skip greetings, small talk, questions, speculation and anything not stated as true.
- Only store the CURRENT state. Never output facts about past, former or previous values (e.g. "Priya was the previous owner", "the deadline used to be Oct 20"). If someone is replacing someone else, output only the new person's fact.
- "subject" is a short, lowercase, canonical label for what the fact is about, starting with the name of the person, team or project, followed by the attribute (e.g. "billing migration deadline", "meera communication tool"). Reuse the same label whenever the same attribute comes up.
- If there is nothing worth remembering, return an empty list.

Return ONLY JSON in this shape:
{"facts": [{"subject": "...", "fact": "..."}]}

Text:
<<TEXT>>
"""

JUDGE_PROMPT = """You maintain an AI assistant's memory. A NEW fact has arrived, and these EXISTING active facts look related to it.

NEW FACT: <<NEW>>

MESSAGE THE NEW FACT CAME FROM (use it to see whether something was replaced):
<<SOURCE>>

EXISTING FACTS:
<<EXISTING>>

Decide how the new fact relates to the existing ones:
- "duplicate": an existing fact already says the same thing (same meaning, even if worded differently).
- "supersede": the new fact replaces or contradicts one or more existing facts because it gives a new value for the same attribute of the same thing (a changed deadline, owner, status, preference or decision). List the ids it replaces in "target_ids".
- "new": the new fact is about something different, or adds information that does not conflict with any existing fact.

If the message says something was switched, moved, replaced or taken over (e.g. "switching from X to Y", "moving from X to Y"), and an existing fact states the old value X, the new fact supersedes it, even though both could be true at once in principle.

Careful: two facts about the same topic are NOT in conflict if they describe different attributes (for example who owns a project vs. its deadline) and can both be true at once.
A new fact that describes a past, former or previous value (e.g. "X was the previous owner") is history, not a replacement: it must never supersede a fact about the current value. In that case answer "duplicate" if the history is already implied, otherwise "new".

Return ONLY JSON: {"decision": "duplicate" | "supersede" | "new", "target_ids": [ids], "reason": "one short sentence"}
"""

ANSWER_PROMPT = """Answer the question using only the memory below. If the memory does not contain the answer, say you don't know. Be concise.

Memory:
<<CONTEXT>>

Question: <<QUESTION>>
"""

VALID_DECISIONS = {"duplicate", "supersede", "new"}


def parse_json(text: str) -> dict:
    """Parse model output as JSON, tolerating code fences and surrounding prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def _retry(fn, attempts: int = 5):
    """Retry on rate limits (429), server errors (5xx) and network blips."""
    delay = 2.0
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            retriable = (
                code == 429
                or (isinstance(code, int) and code >= 500)
                or isinstance(exc, (httpx.TransportError, ConnectionError, TimeoutError))
            )
            if not retriable or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2


class CohereLLM:
    def __init__(self, api_key: str | None = None, client=None):
        if client is None:
            api_key = api_key or os.getenv("COHERE_API_KEY")
            if not api_key:
                raise RuntimeError("COHERE_API_KEY is not set. Add it to your .env file.")
            import cohere

            client = cohere.ClientV2(api_key, timeout=60)
        self.co = client

    # ---- chat ----
    def _chat(self, prompt: str, json_mode: bool = False) -> str:
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        res = _retry(
            lambda: self.co.chat(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                **kwargs,
            )
        )
        return res.message.content[0].text

    def _chat_json(self, prompt: str) -> dict:
        try:
            text = self._chat(prompt, json_mode=True)
        except Exception as exc:
            if getattr(exc, "status_code", None) != 400:
                raise
            text = self._chat(prompt, json_mode=False)  # model without JSON mode
        return parse_json(text)

    # ---- extraction ----
    def extract_facts(self, text: str) -> list[dict]:
        data = self._chat_json(EXTRACT_PROMPT.replace("<<TEXT>>", text))
        facts = []
        for item in data.get("facts", []):
            fact = str(item.get("fact", "")).strip()
            if fact:
                subject = str(item.get("subject", "")).strip().lower() or "general"
                facts.append({"subject": subject, "fact": fact})
        return facts

    # ---- conflict judge ----
    def judge(self, new_fact: dict, candidates: list[dict], source_text: str = "") -> dict:
        existing = "\n".join(
            f"- [id={c['id']}] ({c['created_at'][:10]}) {c['fact']}" for c in candidates
        )
        prompt = (
            JUDGE_PROMPT.replace("<<NEW>>", new_fact["fact"])
            .replace("<<EXISTING>>", existing)
            .replace("<<SOURCE>>", source_text or "(not available)")
        )
        data = self._chat_json(prompt)


        decision = str(data.get("decision", "new")).lower()

        ...
        if decision not in VALID_DECISIONS:
            decision = "new"
        valid_ids = {c["id"] for c in candidates}
        target_ids = []
        for raw in data.get("target_ids", []) or []:
            try:
                tid = int(raw)
            except (TypeError, ValueError):
                continue
            if tid in valid_ids:
                target_ids.append(tid)
        if decision == "supersede" and not target_ids:
            decision = "new"  # nothing valid to replace
        return {
            "decision": decision,
            "target_ids": target_ids,
            "reason": str(data.get("reason", "")),
        }

    # ---- answering (used in Step 6) ----
    def answer(self, question: str, context: str) -> str:
        prompt = ANSWER_PROMPT.replace("<<CONTEXT>>", context).replace(
            "<<QUESTION>>", question
        )
        return self._chat(prompt).strip()

    # ---- embeddings ----
    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            batch = texts[i : i + EMBED_BATCH]
            res = _retry(
                lambda b=batch: self.co.embed(
                    texts=b,
                    model=EMBED_MODEL,
                    input_type=input_type,
                    embedding_types=["float"],
                )
            )
            vectors.extend(res.embeddings.float_)
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed facts that will be stored."""
        return self._embed(texts, "search_document")

    def embed_query(self, text: str) -> list[float]:
        """Embed a search question."""
        return self._embed([text], "search_query")[0]