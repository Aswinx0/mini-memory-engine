"""FastAPI wrapper. Run with:  uvicorn memory_engine.api:app --reload"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .memory import MemoryEngine, build_context


class AddRequest(BaseModel):
    user_id: str
    text: str
    timestamp: Optional[str] = Field(
        default=None, description="ISO timestamp of when this was said (defaults to now)"
    )


class SearchRequest(BaseModel):
    user_id: str
    query: str
    top_k: int = 5
    include_superseded: bool = False


class AskRequest(BaseModel):
    user_id: str
    question: str
    top_k: int = 5


def create_app(engine: Optional[MemoryEngine] = None) -> FastAPI:
    app = FastAPI(title="Mini Memory Engine", version="0.1.0")
    state = {"engine": engine}

    def get_engine() -> MemoryEngine:
        # Built lazily so importing this module doesn't require an API key.
        if state["engine"] is None:
            from .llm import CohereLLM

            state["engine"] = MemoryEngine(CohereLLM(), db_path=os.getenv("MEMORY_DB", "memory.db"))
        return state["engine"]

    @app.post("/add")
    def add(req: AddRequest):
        return get_engine().add(req.user_id, req.text, req.timestamp)

    @app.post("/search")
    def search(req: SearchRequest):
        hits = get_engine().search(req.user_id, req.query, req.top_k, req.include_superseded)
        return {"facts": hits, "context": build_context(hits)}

    @app.post("/ask")
    def ask(req: AskRequest):
        return get_engine().ask(req.user_id, req.question, req.top_k)

    @app.get("/facts")
    def list_facts(user_id: str, include_superseded: bool = True):
        return get_engine().list_facts(user_id, include_superseded)

    @app.delete("/facts/{fact_id}")
    def forget(fact_id: int, user_id: str):
        if not get_engine().forget(fact_id, user_id):
            raise HTTPException(status_code=404, detail="Fact not found for this user")
        return {"deleted": fact_id}

    return app


app = create_app()