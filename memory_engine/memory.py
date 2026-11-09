"""Core memory engine: extract -> reconcile (supersede) -> store -> retrieve."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np

from .db import connect, init_db

CONFLICT_SIM_THRESHOLD = 0.45  # min cosine similarity for a fact to be checked for conflict
CONFLICT_TOP_K = 5             # how many nearby active facts the judge sees
RECENCY_HALF_LIFE_DAYS = 30.0  # the recency bonus halves every 30 days
RECENCY_WEIGHT = 0.1           # how much recency can add to a similarity score


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_iso(ts: Optional[str]) -> str:
    return (_parse(ts) if ts else _utcnow()).isoformat()


def _normalize(vec) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def build_context(hits: list[dict]) -> str:
    """Compact context block to inject into an LLM prompt."""
    if not hits:
        return "(no relevant memories)"
    return "\n".join(f"- [{h['created_at'][:10]}] {h['fact']}" for h in hits)


class MemoryEngine:
    def __init__(self, llm, db_path: str = "memory.db"):
        self.llm = llm
        self.db_path = db_path
        init_db(db_path)

    # ------------------------------------------------------------------ add
    def add(self, user_id: str, text: str, timestamp: Optional[str] = None) -> dict:
        """Extract facts from text, reconcile each against existing memory, store them.

        Assumes facts arrive in chronological order (a newer fact replaces an older one).
        """
        created_at = _to_iso(timestamp)
        result: dict = {"added": [], "superseded": [], "duplicates": []}

        extracted = [f for f in self.llm.extract_facts(text) if f.get("fact")]
        if not extracted:
            return result

        vectors = [
            _normalize(v) for v in self.llm.embed_documents([f["fact"] for f in extracted])
        ]
        # Sequential on purpose: a fact stored earlier in this call can conflict with a later one.
        for item, vec in zip(extracted, vectors):
            self._reconcile_and_store(user_id, item, vec, text, created_at, result)
        return result

    def _reconcile_and_store(self, user_id, item, vec, source_text, created_at, result):
        candidates = self._conflict_candidates(user_id, vec)
        decision = {"decision": "new", "target_ids": []}
        if candidates:
            decision = self.llm.judge(item, candidates, source_text)

        if decision["decision"] == "duplicate":
            result["duplicates"].append(item["fact"])
            return

        new_id = self._insert(user_id, item, vec, source_text, created_at)
        result["added"].append({"id": new_id, "subject": item["subject"], "fact": item["fact"]})

        if decision["decision"] == "supersede":
            target_ids = set(decision["target_ids"])
            old = [c for c in candidates if c["id"] in target_ids]
            if old:
                self._mark_superseded([c["id"] for c in old], new_id, created_at)
                result["superseded"].append(
                    {
                        "new": {"id": new_id, "fact": item["fact"]},
                        "old": [{"id": c["id"], "fact": c["fact"]} for c in old],
                    }
                )

    def _conflict_candidates(self, user_id: str, vec: np.ndarray) -> list[dict]:
        rows = self._fetch(user_id, include_superseded=False)
        if not rows:
            return []
        sims = self._matrix(rows) @ vec
        order = np.argsort(-sims)[:CONFLICT_TOP_K]
        return [
            {
                "id": rows[i]["id"],
                "subject": rows[i]["subject"],
                "fact": rows[i]["fact"],
                "created_at": rows[i]["created_at"],
                "similarity": float(sims[i]),
            }
            for i in order
            if sims[i] >= CONFLICT_SIM_THRESHOLD
        ]

    # --------------------------------------------------------------- search
    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        include_superseded: bool = False,
        min_similarity: float = 0.0,
        now: Optional[datetime] = None,
    ) -> list[dict]:
        """Return the most relevant facts: similarity plus a small recency bonus."""
        rows = self._fetch(user_id, include_superseded)
        if not rows:
            return []
        sims = self._matrix(rows) @ _normalize(self.llm.embed_query(query))
        now = now or _utcnow()

        hits = []
        for row, sim in zip(rows, sims):
            if sim < min_similarity:
                continue
            age_days = max((now - _parse(row["created_at"])).total_seconds() / 86400, 0.0)
            recency = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)
            hits.append(
                {
                    "id": row["id"],
                    "subject": row["subject"],
                    "fact": row["fact"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "similarity": round(float(sim), 4),
                    "score": round(float(sim) + RECENCY_WEIGHT * recency, 4),
                }
            )
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]

    def ask(
        self,
        user_id: str,
        question: str,
        top_k: int = 5,
        include_superseded: bool = False,
    ) -> dict:
        """Retrieve memory for the question and let the LLM answer from it (used in Step 6)."""
        hits = self.search(user_id, question, top_k, include_superseded)
        context = build_context(hits)
        return {"answer": self.llm.answer(question, context), "context": context, "facts": hits}

    # ------------------------------------------------------- list / forget
    def list_facts(self, user_id: str, include_superseded: bool = True) -> list[dict]:
        return [
            {
                "id": r["id"],
                "subject": r["subject"],
                "fact": r["fact"],
                "status": r["status"],
                "created_at": r["created_at"],
                "superseded_by": r["superseded_by"],
                "superseded_at": r["superseded_at"],
            }
            for r in self._fetch(user_id, include_superseded)
        ]

    def forget(self, fact_id: int, user_id: Optional[str] = None) -> bool:
        """Delete one fact. If user_id is given, only that user's fact can be deleted."""
        sql, params = "DELETE FROM facts WHERE id = ?", [fact_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        with connect(self.db_path) as conn:
            return conn.execute(sql, params).rowcount > 0

    # ------------------------------------------------------------ internals
    def _fetch(self, user_id: str, include_superseded: bool):
        sql = "SELECT * FROM facts WHERE user_id = ?"
        if not include_superseded:
            sql += " AND status = 'active'"
        sql += " ORDER BY id"
        with connect(self.db_path) as conn:
            return conn.execute(sql, (user_id,)).fetchall()

    @staticmethod
    def _matrix(rows) -> np.ndarray:
        return np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])

    def _insert(self, user_id, item, vec: np.ndarray, source_text, created_at) -> int:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO facts (user_id, subject, fact, embedding, source_text, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    item["subject"],
                    item["fact"],
                    vec.astype(np.float32).tobytes(),
                    source_text,
                    created_at,
                ),
            )
            return cur.lastrowid

    def _mark_superseded(self, old_ids: list[int], new_id: int, at: str) -> None:
        with connect(self.db_path) as conn:
            conn.executemany(
                "UPDATE facts SET status = 'superseded', superseded_by = ?, superseded_at = ?"
                " WHERE id = ?",
                [(new_id, at, oid) for oid in old_ids],
            )