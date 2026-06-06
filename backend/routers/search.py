from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.security import get_current_user
from services.cache import cache_get, cache_set

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:         str
    course_code:   Optional[str] = None
    year:          Optional[int] = None
    semester:      Optional[str] = None
    question_type: Optional[str] = None   # calculation | theory | diagram | table
    min_marks:     Optional[int] = None
    top_k:         int           = 20
    rerank_top_n:  int           = 5
    alpha:         float         = 0.7    # 0=sparse only, 1=dense only


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/search")
def search(
    body:         SearchRequest,
    request:      Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Standard search — returns full JSON response.
    Use this for simple queries where streaming is not needed.
    """
    svc = request.app.state.retrieval

    filters = svc.build_filter(
        body.course_code, body.year, body.semester,
        body.question_type, body.min_marks,
    )

    # Check cache first
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


@router.post("/search/stream")
def search_stream(
    body:         SearchRequest,
    request:      Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming search — returns Server-Sent Events.

    Client receives events in this order:
      1. { type: 'sources', sources: [...] }   ← show sources immediately
      2. { type: 'token',   token:   '...' }   ← answer tokens stream in
      3. { type: 'done' }                       ← stream finished
      4. { type: 'error',   message: '...' }   ← only on failure

    Usage with fetch() in React:
      const res = await fetch('/api/search/stream', { method:'POST', body:... })
      const reader = res.body.getReader()
      // read chunks, parse 'data: {...}' lines
    """
    svc = request.app.state.retrieval

    filters = svc.build_filter(
        body.course_code, body.year, body.semester,
        body.question_type, body.min_marks,
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
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",   # disable nginx buffering
        },
    )

@router.post("/search/agent")
def agent_search(
    body:         SearchRequest,
    request:      Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Intent-aware search. Routes to the right handler based on query type.
    Always streams SSE.
    """
    from services.intent import classify
    from services.agents import handle

    intent = classify(body.query)
    svc    = request.app.state.retrieval

    def event_generator():
        # First event always tells the frontend what mode we're in
        import json
        yield f"data: {json.dumps({'type': 'intent', 'intent': intent.type, 'slots': intent.slots})}\n\n"
        yield from handle(intent, body, svc)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )