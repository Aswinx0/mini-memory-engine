DEADLINE_OLD = "billing migration deadline :: The billing migration deadline is Oct 20"
DEADLINE_NEW = "billing migration deadline :: The billing migration deadline is Nov 3"
OWNER = "billing migration owner :: Priya owns the billing migration"


def test_contradiction_supersedes_old_fact(engine):
    engine.add("u1", DEADLINE_OLD, timestamp="2026-10-01")
    res = engine.add("u1", DEADLINE_NEW, timestamp="2026-10-08")

    assert len(res["superseded"]) == 1
    active = engine.list_facts("u1", include_superseded=False)
    assert [f["fact"] for f in active] == ["The billing migration deadline is Nov 3"]

    everything = engine.list_facts("u1", include_superseded=True)
    assert len(everything) == 2
    old = next(f for f in everything if f["status"] == "superseded")
    assert old["superseded_by"] == active[0]["id"]


def test_search_returns_only_current_fact_by_default(engine):
    engine.add("u1", DEADLINE_OLD, timestamp="2026-10-01")
    engine.add("u1", DEADLINE_NEW, timestamp="2026-10-08")

    hits = engine.search("u1", "billing migration deadline")
    assert [h["fact"] for h in hits] == ["The billing migration deadline is Nov 3"]

    hits_all = engine.search("u1", "billing migration deadline", include_superseded=True)
    assert len(hits_all) == 2


def test_duplicate_fact_is_not_stored_twice(engine):
    engine.add("u1", DEADLINE_NEW, timestamp="2026-10-01")
    res = engine.add("u1", DEADLINE_NEW, timestamp="2026-10-02")

    assert res["duplicates"] == ["The billing migration deadline is Nov 3"]
    assert len(engine.list_facts("u1")) == 1


def test_different_attribute_is_not_a_conflict(engine):
    engine.add("u1", DEADLINE_NEW, timestamp="2026-10-01")
    res = engine.add("u1", OWNER, timestamp="2026-10-02")

    assert res["superseded"] == []
    assert len(engine.list_facts("u1", include_superseded=False)) == 2


def test_conflict_inside_one_add_call(engine):
    # Both facts arrive in the same text; the later one must replace the earlier one.
    res = engine.add("u1", DEADLINE_OLD + "\n" + DEADLINE_NEW, timestamp="2026-10-01")

    assert len(res["superseded"]) == 1
    active = engine.list_facts("u1", include_superseded=False)
    assert [f["fact"] for f in active] == ["The billing migration deadline is Nov 3"]


def test_forget_deletes_and_respects_user(engine):
    engine.add("u1", OWNER)
    fact_id = engine.list_facts("u1")[0]["id"]

    assert engine.forget(fact_id, user_id="someone-else") is False
    assert len(engine.list_facts("u1")) == 1

    assert engine.forget(fact_id, user_id="u1") is True
    assert engine.list_facts("u1") == []


def test_users_do_not_see_each_others_memory(engine):
    engine.add("u1", OWNER)
    assert engine.search("u2", "who owns the billing migration") == []
    assert engine.list_facts("u2") == []


def test_ask_builds_context_from_active_facts_only(engine):
    engine.add("u1", DEADLINE_OLD, timestamp="2026-10-01")
    engine.add("u1", DEADLINE_NEW, timestamp="2026-10-08")

    out = engine.ask("u1", "billing migration deadline")
    assert "Nov 3" in out["context"]
    assert "Oct 20" not in out["context"]


def test_empty_memory_search(engine):
    assert engine.search("nobody", "anything") == []
    assert engine.ask("nobody", "anything")["context"] == "(no relevant memories)"