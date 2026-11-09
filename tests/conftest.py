import hashlib
import re

import numpy as np
import pytest

from memory_engine.memory import MemoryEngine


class FakeLLM:
    """Deterministic stand-in for Cohere so the engine logic can be tested offline.

    Input lines look like:  "<subject> :: <fact sentence>"
    """

    DIM = 128

    def extract_facts(self, text):
        facts = []
        for line in text.splitlines():
            if "::" in line:
                subject, fact = (p.strip() for p in line.split("::", 1))
                facts.append({"subject": subject.lower(), "fact": fact})
        return facts

    def _vec(self, text):
        v = np.zeros(self.DIM, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.DIM] += 1
        return v.tolist()

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    def judge(self, new_fact, candidates, source_text=""):
        same = [c for c in candidates if c["subject"] == new_fact["subject"]]
        if not same:
            return {"decision": "new", "target_ids": []}
        if any(c["fact"] == new_fact["fact"] for c in same):
            return {"decision": "duplicate", "target_ids": []}
        return {"decision": "supersede", "target_ids": [c["id"] for c in same]}

    def answer(self, question, context):
        return context


@pytest.fixture
def engine(tmp_path):
    return MemoryEngine(FakeLLM(), db_path=str(tmp_path / "test.db"))