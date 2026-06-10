"""
services/agent/graph.py
───────────────────────
LangGraph StateGraph definition, per-thread SQLite checkpointer, and
the routing logic that maps an intent to the correct handler node.

Exports:
    build_workflow() → StateGraph   (called once at module level)
    get_saver()      → SqliteSaver  (per-thread, called inside handle())
"""

import json
import threading
from typing import Annotated, Any

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from services.intent import classify_with_memory
import services.agent.handlers as h

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from core.config import settings

# ── 1. State ──────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ── 2. Thread-local run context ───────────────────────────────────────────────
#
# Holds non-serialisable objects (intent, body, svc, generator) for the
# duration of a single graph invocation.  Never written to the checkpoint.

_run_ctx = threading.local()


# ── 3. Nodes ──────────────────────────────────────────────────────────────────

def analyze_intent_node(state: AgentState) -> dict:
    intent = classify_with_memory(state["messages"])
    _run_ctx.intent = intent
    return {}


def _make_execution_node(handler_fn):
    def node(state: AgentState) -> dict:
        intent = _run_ctx.intent
        body   = _run_ctx.body
        svc    = _run_ctx.svc
        _run_ctx.generator = handler_fn(intent, body, svc)
        memory_note = AIMessage(
            content=(
                f"[system:executed {intent.type} "
                f"slots={json.dumps(intent.slots)}]"
            )
        )
        return {"messages": [memory_note]}
    return node


# ── 4. Routing ────────────────────────────────────────────────────────────────

_VALID_INTENTS = {
    "fetch_paper", "topic_search", "tutor_mode",
    "trend_analysis", "general_knowledge", "rag_search",
}


def _route_intent(state: AgentState) -> str:
    intent = getattr(_run_ctx, "intent", None)
    intent_type = intent.type if intent else "rag_search"
    return intent_type if intent_type in _VALID_INTENTS else "rag_search"


# ── 5. Graph builder ──────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    wf = StateGraph(AgentState)

    wf.add_node("analyze_intent",    analyze_intent_node)
    wf.add_node("fetch_paper",       _make_execution_node(h.fetch_paper))
    wf.add_node("topic_search",      _make_execution_node(h.topic_search))
    wf.add_node("tutor_mode",        _make_execution_node(h.tutor_mode))
    wf.add_node("trend_analysis",    _make_execution_node(h.trend_analysis))
    wf.add_node("general_knowledge", _make_execution_node(h.general_knowledge))
    wf.add_node("rag_search",        _make_execution_node(h.rag_search))

    wf.add_edge(START, "analyze_intent")
    wf.add_conditional_edges("analyze_intent", _route_intent)

    for name in _VALID_INTENTS:
        wf.add_edge(name, END)

    return wf


# ── 6. Per-thread SQLite checkpointer ────────────────────────────────────────

_local    = threading.local()

def get_saver() -> PostgresSaver:
    """Return a per-thread PostgresSaver, creating it on first access."""
    if not hasattr(_local, "saver"):
        conn = psycopg.connect(settings.database_url, autocommit=True)
        saver = PostgresSaver(conn)
        saver.setup()   # creates langgraph checkpoint tables if absent
        _local.saver = saver
    return _local.saver