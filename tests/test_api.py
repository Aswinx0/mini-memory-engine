from fastapi.testclient import TestClient

from memory_engine.api import create_app


def test_api_add_search_list_forget(engine):
    client = TestClient(create_app(engine))
    old = "deadline :: The billing migration deadline is Oct 20"
    new = "deadline :: The billing migration deadline is Nov 3"

    client.post("/add", json={"user_id": "u1", "text": old, "timestamp": "2026-10-01"})
    r = client.post("/add", json={"user_id": "u1", "text": new, "timestamp": "2026-10-08"})
    assert r.status_code == 200
    assert len(r.json()["superseded"]) == 1

    r = client.post("/search", json={"user_id": "u1", "query": "billing migration deadline"})
    assert [f["fact"] for f in r.json()["facts"]] == ["The billing migration deadline is Nov 3"]
    assert "Nov 3" in r.json()["context"]

    facts = client.get("/facts", params={"user_id": "u1"}).json()
    assert len(facts) == 2

    active_id = next(f["id"] for f in facts if f["status"] == "active")
    assert client.delete(f"/facts/{active_id}", params={"user_id": "other"}).status_code == 404
    assert client.delete(f"/facts/{active_id}", params={"user_id": "u1"}).status_code == 200


def test_api_ask(engine):
    client = TestClient(create_app(engine))
    client.post("/add", json={"user_id": "u1", "text": "owner :: Priya owns the billing migration"})
    r = client.post("/ask", json={"user_id": "u1", "question": "who owns the billing migration"})
    assert r.status_code == 200
    assert "Priya" in r.json()["answer"]