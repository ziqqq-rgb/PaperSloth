"""
routers/search.py
─────────────────
Search endpoints for PaperSloth.

  POST /search           → standard JSON response (cached)
  POST /search/stream    → SSE streaming (legacy, direct retrieval)
  POST /search/agent     → SSE streaming (intent-aware, multi-turn memory)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.security import get_current_user
from services.cache import cache_get, cache_set

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:         str
    course_code:   Optional[str]   = None
    year:          Optional[int]   = None
    semester:      Optional[str]   = None
    question_type: Optional[str]   = None   # calculation | theory | diagram | table
    min_marks:     Optional[int]   = None
    top_k:         int             = 20
    rerank_top_n:  int             = 5
    alpha:         float           = 0.7    # 0 = sparse only, 1 = dense only


# ── POST /search  (standard JSON) ─────────────────────────────────────────────

@router.post("/search")
def search(
    body:         SearchRequest,
    request:      Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Standard search — returns full JSON response.
    Response is cached in Redis by (query, filters) key.
    """
    svc = request.app.state.retrieval

    filters = svc.build_filter(
        body.course_code,
        body.year,
        body.semester,
        body.question_type,
        body.min_marks,
    )

    cached = cache_get(body.query, filters)
    if cached:
        cached["cached"] = True
        return cached

    result = svc.search(
        query        = body.query,
        filters      = filters,
        top_k        = body.top_k,
        rerank_top_n = body.rerank_top_n,
        alpha        = body.alpha,
    )

    cache_set(body.query, filters, result)
    return result


# ── POST /search/stream  (SSE, direct retrieval — no agent) ──────────────────

@router.post("/search/stream")
def search_stream(
    body:         SearchRequest,
    request:      Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming search using the retrieval pipeline directly (no intent routing).

    Client receives SSE events in order:
      1. { type: 'sources', sources: [...] }
      2. { type: 'token',   token:   '...' }  (repeated)
      3. { type: 'done' }
      4. { type: 'error',   message: '...' }  (only on failure)
    """
    svc = request.app.state.retrieval

    filters = svc.build_filter(
        body.course_code,
        body.year,
        body.semester,
        body.question_type,
        body.min_marks,
    )

    def event_generator():
        yield from svc.stream(
            query        = body.query,
            filters      = filters,
            top_k        = body.top_k,
            rerank_top_n = body.rerank_top_n,
            alpha        = body.alpha,
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── POST /search/agent  (SSE, intent-aware, multi-turn memory) ────────────────

@router.post("/search/agent")
def agent_search(
    body:         SearchRequest,
    request:      Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Intent-aware streaming search backed by the LangGraph agent.

    Memory is scoped per user: thread_id = current_user["id"].
    Follow-up questions ("what about part b?", "and Q3?") automatically
    inherit context from the user's previous turns in this session.

    SSE event stream:
      1. { type: 'intent',  intent: '...', slots: {...} }
      2. { type: 'sources', sources: [...] }              (most intents)
      3. { type: 'token',   token:   '...' }              (repeated)
      4. { type: 'done' }
      5. { type: 'error',   message: '...' }              (only on failure)
      6. { type: 'tutor_start', ... }                     (tutor_mode only)
    """
    from services.agents import handle  # late import avoids circular deps at startup

    svc       = request.app.state.retrieval
    # Scope memory to the authenticated user so histories never bleed across users
    thread_id = current_user["id"]

    def event_generator():
        yield from handle(
            query     = body.query,
            body      = body,
            svc       = svc,
            thread_id = thread_id,
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )