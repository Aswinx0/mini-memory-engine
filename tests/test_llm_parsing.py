"""Checks the Cohere wrapper's parsing/validation using a stubbed client (no network)."""
from types import SimpleNamespace

from memory_engine.llm import CohereLLM, parse_json


class StubClient:
    def __init__(self, chat_text="{}"):
        self.chat_text = chat_text
        self.chat_calls = []

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=[SimpleNamespace(text=self.chat_text)]))

    def embed(self, texts, **kwargs):
        vectors = [[float(len(t)), 1.0] for t in texts]
        return SimpleNamespace(embeddings=SimpleNamespace(float_=vectors))


def test_parse_json_handles_fences_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! Here it is: {"a": 2} hope that helps') == {"a": 2}


def test_extract_facts_cleans_output():
    stub = StubClient(
        '{"facts": [{"subject": "Billing Deadline", "fact": "The deadline is Nov 3."},'
        ' {"subject": "x", "fact": "  "}, {"fact": "No subject given."}]}'
    )
    facts = CohereLLM(client=stub).extract_facts("anything")
    assert facts == [
        {"subject": "billing deadline", "fact": "The deadline is Nov 3."},
        {"subject": "general", "fact": "No subject given."},
    ]


def test_judge_drops_unknown_ids_and_downgrades_empty_supersede():
    candidates = [{"id": 1, "fact": "Deadline is Oct 20.", "created_at": "2026-10-01T00:00:00+00:00"}]

    stub = StubClient('{"decision": "supersede", "target_ids": [1, 99], "reason": "changed"}')
    out = CohereLLM(client=stub).judge({"fact": "Deadline is Nov 3."}, candidates)
    assert out["decision"] == "supersede" and out["target_ids"] == [1]

    stub = StubClient('{"decision": "supersede", "target_ids": [99]}')
    assert CohereLLM(client=stub).judge({"fact": "x"}, candidates)["decision"] == "new"

    stub = StubClient('{"decision": "banana"}')
    assert CohereLLM(client=stub).judge({"fact": "x"}, candidates)["decision"] == "new"


def test_embeddings_are_batched_and_returned():
    llm = CohereLLM(client=StubClient())
    assert llm.embed_documents(["ab", "abc"]) == [[2.0, 1.0], [3.0, 1.0]]
    assert llm.embed_query("abcd") == [4.0, 1.0]