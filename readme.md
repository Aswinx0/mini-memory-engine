# Mini Memory Engine for AI Agents

A small memory layer for LLM agents. It stores **facts instead of raw text** and keeps them **up to date**: when new information contradicts an old fact, the old fact is marked *superseded* (not deleted), so retrieval returns what is currently true while the history is kept.

Built with Python, FastAPI, SQLite, NumPy and Cohere (LLM + embeddings).

> This is a learning project and a focused slice of a hard problem, not a production system. See [Limitations](#limitations).

## The problem

LLM apps forget everything between sessions. The common fix is to store old chats in a vector DB and retrieve similar chunks. That breaks when information changes: the agent retrieves both *"deadline is Oct 20"* and *"deadline moved to Nov 3"* and cannot tell which one is true.

## How it works

**Write path (`add`)**

1. **Extract**: an LLM turns text into atomic, self-contained facts: `{subject, fact}`.
2. **Embed**: each fact is embedded (Cohere `embed-english-v3.0`, 1024 dims) and normalized.
3. **Find candidates**: among the user's *active* facts, take the top 5 with cosine similarity >= 0.45.
4. **Judge**: an LLM sees the new fact, the candidates and the original message, and returns `new`, `duplicate` or `supersede` (with target ids). Invalid output (unknown ids, bad decisions) is cleaned up in code so a bad answer can never delete the wrong fact.
5. **Store**: the fact is saved to SQLite. Superseded rows get `status = 'superseded'`, `superseded_by` and `superseded_at`.

**Read path (`search` / `ask`)**

1. Embed the question.
2. Score only *active* facts: `similarity + 0.1 * recency` (recency halves every 30 days).
3. Return the top-k as a compact context block for the LLM prompt.

Example:

```
=== Session 2026-10-01 ===
  + stored #1: Priya is the owner of the billing migration.
  + stored #2: The billing migration deadline is Oct 20.
=== Session 2026-10-08 ===
  + stored #4: The billing migration deadline is Nov 3.
  ~ superseded #2: The billing migration deadline is Oct 20.
      by #4: The billing migration deadline is Nov 3.
Q: When is the billing migration deadline?
A: The billing migration deadline is Nov 3.
```

## Project structure

```
memory_engine/
  db.py        SQLite schema and connection helper
  llm.py       Cohere wrapper: extraction, conflict judge, embeddings, answering
  memory.py    MemoryEngine: add / search / ask / list_facts / forget
  api.py       FastAPI endpoints
cli.py         CLI and scripted demo
eval_data.py   Evaluation scenarios
run_eval.py    Evaluation: no memory vs plain RAG vs memory engine
tests/         Offline tests using a deterministic FakeLLM
```

## Setup

```bash
python -m venv venv
# Windows PowerShell: venv\Scripts\Activate.ps1      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`):

```
COHERE_API_KEY=your-key-here
```

## Usage

```bash
python cli.py demo                                    # two-session scripted demo
python cli.py add --user aswin "Priya owns the billing migration."
python cli.py search --user aswin "who owns billing?"
python cli.py ask --user aswin "When is the billing deadline?"
python cli.py list --user aswin
python cli.py forget --user aswin 3

uvicorn memory_engine.api:app --reload                # API docs at http://127.0.0.1:8000/docs
```

API: `POST /add`, `POST /search`, `POST /ask`, `GET /facts`, `DELETE /facts/{id}`. Every call is scoped by `user_id`.

## Tests

```bash
python -m pytest -q
```

15 offline tests (no API calls) use a deterministic `FakeLLM` and cover: superseding, duplicate handling, different attributes not conflicting, conflicts inside one message, per-user isolation, `forget`, API endpoints, and validation of malformed LLM output. These test the engine's logic around the LLM, not the quality of the LLM's judgements. That is what the eval is for.

## Evaluation

`run_eval.py` replays multi-session conversations in which facts change, then asks questions and compares three methods:

- **No memory**: the LLM answers with no context.
- **Plain RAG**: sentence chunks from every session are embedded and the top 3 are retrieved. Nothing is ever updated.
- **Memory engine**: top 3 from the active facts.

Scoring is strict text matching (`any_of` / `none_of` lists), so some correct answers phrased unexpectedly can be marked wrong.

Latest run, after all four prompt/judge fixes (5 of 6 scenarios, 17 questions; the run stopped at the 6th scenario when the Cohere trial quota ran out, so the final 3 questions were not run. The terminal log is saved in `eval_log_2026-11-23.txt`):

| Method | Correct |
|---|---|
| No memory | 0/17 (0%) |
| Plain RAG | 15/17 (88%) |
| Memory engine | 17/17 (100%) |

Earlier complete runs, before the final fixes (14-20 questions): the engine scored roughly 80-93% and plain RAG 79-90%, with results varying by a question or two between runs.

**How to read this:** the latest run is the engine's best, and it is encouraging, but it is a single run on 17 questions that I wrote and tuned against. The earlier runs showed no reliable advantage over plain RAG, and LLM extraction varies between runs. The 6th scenario (`kiran`) was written after the first fixes and is the closest thing to a held-out test, and it has not yet been run on the final code. Each scenario has only 2-3 sessions, so a top-3 retriever sees almost the whole history. Longer histories with many updates to the same fact are the next experiment.

### What the eval found

Inspecting the stored facts after each failure showed the problems were in extraction and judging, not retrieval:

1. **Change stored as a "reason"**: "switching from Stripe to Razorpay because of lower fees" produced a *reason* fact but no new-provider fact, so Stripe was never replaced. Fixed by tightening the extraction prompt.
2. **Dropped entity names**: facts like "The team communication tool is Teams" had no person in them, so labels did not match and nothing was superseded. Fixed by requiring every fact to name its subject.
3. **History overriding current facts**: "Priya was the previous owner" superseded "Rahul is the owner". Fixed by telling the extractor to store only current state and the judge never to let a past-value fact replace a current one.
4. **Judge lacked context**: "Stripe" and "Razorpay" can both be true in isolation. The proof of replacement was in the original sentence, so the judge now receives the source message. With this change, all billing, Meera, mobile app, Ishan and analytics-team questions passed in the latest run (17/17).
5. **Ambiguous scenario**: one test scenario never named the team in later sessions, so no method could link them. It was rewritten, and this is disclosed here.

The extraction prompt was tuned four times after seeing failures, so the scores above are not a clean held-out measurement.

Plain RAG's failures were not all about stale data either: sentences like "Her new team lead is Sana" do not contain the person's name, so retrieval missed them. Part of the engine's benefit is that extraction writes self-contained facts.

## Limitations

- Assumes facts arrive in chronological order. Out-of-order updates are not handled.
- Extraction sees only the current message, so implicit references across sessions ("the database is now X") can fail to match the right fact. Passing existing facts into extraction is the planned fix.
- Brute-force cosine search over a NumPy matrix is O(n) per query. Fine for thousands of facts per user; beyond that use pgvector or a vector DB.
- `user_id` is trusted from the client. There is no authentication or team/org scoping.
- Each `add` costs one extraction call plus one judge call per fact that has similar neighbours.
- Extraction and judging are non-deterministic LLM calls, so results vary between runs.

## Future work

- Entity resolution in extraction (pass existing facts as context).
- Timestamps-aware superseding for out-of-order facts, and valid-from / valid-to per fact.
- Hybrid keyword + vector search with reranking.
- Authentication and team/org-level permissions.
- Longer-history benchmark (accuracy vs. number of updates per fact) with more scenarios.