"""Command-line interface and demo.

  python cli.py demo
  python cli.py add --user aswin "Priya owns the billing migration."
  python cli.py search --user aswin "who owns billing?"
  python cli.py ask --user aswin "When is the billing deadline?"
  python cli.py list --user aswin [--active]
  python cli.py forget --user aswin 3
"""
from __future__ import annotations

import argparse
import os

from memory_engine import MemoryEngine, build_context

DB = os.getenv("MEMORY_DB", "memory.db")


def make_engine(db_path: str = DB) -> MemoryEngine:
    from memory_engine.llm import CohereLLM

    return MemoryEngine(CohereLLM(), db_path=db_path)


def show_add_result(res: dict) -> None:
    for f in res["added"]:
        print(f"  + stored #{f['id']}: {f['fact']}")
    for s in res["superseded"]:
        for old in s["old"]:
            print(f"  ~ superseded #{old['id']}: {old['fact']}")
            print(f"      by #{s['new']['id']}: {s['new']['fact']}")
    for d in res["duplicates"]:
        print(f"  = duplicate skipped: {d}")
    if not (res["added"] or res["duplicates"]):
        print("  (nothing worth remembering)")


def show_facts(facts: list[dict]) -> None:
    if not facts:
        print("  (empty)")
    for f in facts:
        tag = "ACTIVE    " if f["status"] == "active" else "superseded"
        extra = f"  -> replaced by #{f['superseded_by']}" if f.get("superseded_by") else ""
        print(f"  #{f['id']:<3} {tag} [{f['created_at'][:10]}] {f['fact']}{extra}")


def run_demo() -> None:
    if os.path.exists("demo.db"):
        os.remove("demo.db")  # fresh start each run
    eng = make_engine("demo.db")
    user = "demo-user"

    sessions = [
        (
            "2026-10-01",
            "Priya is the owner of the billing migration. The deadline is Oct 20. "
            "We decided to use Stripe for payments.",
        ),
        (
            "2026-10-08",
            "Quick update: the billing migration deadline moved to Nov 3, and "
            "Rahul is taking over the migration from Priya.",
        ),
    ]
    for ts, text in sessions:
        print(f"\n=== Session {ts} ===\n  \"{text}\"")
        show_add_result(eng.add(user, text, timestamp=ts))

    print("\n=== Memory after both sessions ===")
    show_facts(eng.list_facts(user))

    for q in ["Who owns the billing migration?", "When is the billing migration deadline?"]:
        out = eng.ask(user, q)
        print(f"\nQ: {q}\nContext sent to the LLM:\n{out['context']}\nA: {out['answer']}")


def main() -> None:
    p = argparse.ArgumentParser(description="Mini memory engine CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo", help="run a scripted two-session demo")

    a = sub.add_parser("add")
    a.add_argument("--user", required=True)
    a.add_argument("--time", help="ISO timestamp (default: now)")
    a.add_argument("text")

    s = sub.add_parser("search")
    s.add_argument("--user", required=True)
    s.add_argument("--top-k", type=int, default=5)
    s.add_argument("--all", action="store_true", help="include superseded facts")
    s.add_argument("query")

    q = sub.add_parser("ask")
    q.add_argument("--user", required=True)
    q.add_argument("question")

    ls = sub.add_parser("list")
    ls.add_argument("--user", required=True)
    ls.add_argument("--active", action="store_true", help="hide superseded facts")

    f = sub.add_parser("forget")
    f.add_argument("--user", required=True)
    f.add_argument("fact_id", type=int)

    args = p.parse_args()
    if args.cmd == "demo":
        return run_demo()

    eng = make_engine()
    if args.cmd == "add":
        show_add_result(eng.add(args.user, args.text, args.time))
    elif args.cmd == "search":
        hits = eng.search(args.user, args.query, args.top_k, include_superseded=args.all)
        print(build_context(hits))
    elif args.cmd == "ask":
        out = eng.ask(args.user, args.question)
        print(f"Context:\n{out['context']}\n\nAnswer: {out['answer']}")
    elif args.cmd == "list":
        show_facts(eng.list_facts(args.user, include_superseded=not args.active))
    elif args.cmd == "forget":
        ok = eng.forget(args.fact_id, args.user)
        print("deleted" if ok else "not found for this user")


if __name__ == "__main__":
    main()