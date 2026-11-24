"""Evaluation: no memory vs plain RAG vs memory engine.  Run:  python run_eval.py"""
from __future__ import annotations

import json
import os
import re
import time

import numpy as np

from eval_data import SCENARIOS
from memory_engine import MemoryEngine
from memory_engine.llm import CohereLLM

TOP_K = 3
PAUSE = 2.0  # seconds between questions, to stay under Cohere rate limits
DB = "eval.db"


def has_word(text: str, word: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"\b", text, re.I) is not None


MONTHS = {"january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr", "june": "Jun",
          "july": "Jul", "august": "Aug", "september": "Sep", "october": "Oct",
          "november": "Nov", "december": "Dec"}


def normalize(text: str) -> str:
    for full, short in MONTHS.items():
        text = re.sub(r"\b" + full + r"\b", short, text, flags=re.I)
    return text


def is_correct(answer: str, any_of: list[str], none_of: list[str]) -> bool:
    answer = normalize(answer)
    right = any(has_word(answer, w) for w in any_of)
    stale = any(has_word(answer, w) for w in none_of)
    return right and not stale


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


class PlainRAG:
    """Baseline: sentence chunks from every session, embedded, top-k retrieval. Never updates."""

    def __init__(self, llm: CohereLLM, sessions):
        self.llm = llm
        self.chunks = [(date, s) for date, text in sessions for s in split_sentences(text)]
        vecs = np.array(llm.embed_documents([s for _, s in self.chunks]), dtype=np.float32)
        self.vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    def context(self, question: str, top_k: int = TOP_K) -> str:
        q = np.array(self.llm.embed_query(question), dtype=np.float32)
        q /= np.linalg.norm(q)
        order = np.argsort(-(self.vecs @ q))[:top_k]
        return "\n".join(f"- [{self.chunks[i][0]}] {self.chunks[i][1]}" for i in order)


def main() -> None:
    if os.path.exists(DB):
        os.remove(DB)
    llm = CohereLLM()
    engine = MemoryEngine(llm, db_path=DB)

    methods = ["no_memory", "plain_rag", "memory_engine"]
    totals = {m: 0 for m in methods}
    results = []
    n = 0

    for sc in SCENARIOS:
        user = sc["name"]
        print(f"\n### {user}")
        for date, text in sc["sessions"]:
            engine.add(user, text, timestamp=date)
        rag = PlainRAG(llm, sc["sessions"])

        for item in sc["questions"]:
            q = item["q"]
            answers = {
                "no_memory": llm.answer(q, "(no memory available)"),
                "plain_rag": llm.answer(q, rag.context(q)),
                "memory_engine": engine.ask(user, q, top_k=TOP_K)["answer"],
            }
            row = {"scenario": user, "question": q}
            marks = []
            for m in methods:
                ok = is_correct(answers[m], item["any_of"], item["none_of"])
                totals[m] += int(ok)
                row[m] = {"answer": answers[m], "correct": ok}
                marks.append(f"{m}={'OK' if ok else 'X '}")
            n += 1
            results.append(row)
            print(f"  {q}\n     " + "  ".join(marks))
            for m in ("plain_rag", "memory_engine"):
                if not row[m]["correct"]:
                    print(f"     [{m} said] {answers[m][:140]}")
            time.sleep(PAUSE)

    print("\n=== RESULTS ===")
    for m in methods:
        print(f"  {m:<14} {totals[m]}/{n}  ({100 * totals[m] / n:.0f}%)")

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump({"n": n, "totals": totals, "rows": results}, f, indent=2)
    print("\nFull answers saved to results.json")


if __name__ == "__main__":
    main()