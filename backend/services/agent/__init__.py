"""
services/agent/__init__.py
──────────────────────────
Public entry point for the LangGraph agent.

Called by routers/search.py:
    from services.agents import handle
    yield from handle(query, body, svc, thread_id)
"""

import json
from typing import Any, Generator

from langchain_core.messages import HumanMessage

from services.agent.graph import AgentState, _run_ctx, build_workflow, get_saver

# Compile once at import time; re-compiled per request with a fresh checkpointer.
_workflow = build_workflow()


def handle(
    query:     str,
    body:      Any,
    svc:       Any,
    thread_id: str,
) -> Generator[str, None, None]:
    """
    Invoke the agent for one user turn and yield SSE-formatted events.

    thread_id scopes SQLite memory to the authenticated user so histories
    never bleed across users.
    """
    config = {"configurable": {"thread_id": thread_id}}

    _run_ctx.body      = body
    _run_ctx.svc       = svc
    _run_ctx.intent    = None
    _run_ctx.generator = None

    initial_state: AgentState = {"messages": [HumanMessage(content=query)]}

    app = _workflow.compile(checkpointer=get_saver())
    app.invoke(initial_state, config=config)

    intent = getattr(_run_ctx, "intent", None)
    if intent:
        yield f"data: {json.dumps({'type': 'intent', 'intent': intent.type, 'slots': intent.slots})}\n\n"

    gen = getattr(_run_ctx, "generator", None)
    if gen:
        yield from gen
    else:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent produced no output.'})}\n\n"