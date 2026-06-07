"""
services/agents.py
──────────────────
LangGraph-based multi-turn agent for PaperSloth.

Graph structure
───────────────
  START
    └─► analyze_intent          (classify query using full history)
          └─► [conditional]
                ├─► fetch_paper
                ├─► topic_search
                ├─► tutor_mode
                ├─► trend_analysis
                ├─► general_knowledge
                └─► rag_search
                      └─► END

Memory
──────
Per-user SQLite checkpointing via thread_id = user_id from the JWT.
Each invocation loads the user's prior messages from SQLite before
classifying, so follow-up questions work naturally.

Public API
──────────
handle(query, body, svc, thread_id) → Generator[str, None, None]
    Called by routers/search.py.  Yields SSE-formatted strings.

TUTOR_SYSTEM
    Exported constant used by services/retrieval.py.
"""

import json
import re
import sqlite3
import threading
from typing import Annotated, Any, Generator, Optional

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from core.config import settings
from core.database import execute_query
from services.intent import Intent, classify_with_memory

# ── 1. LangGraph state ────────────────────────────────────────────────────────
#
# `messages`  — appended automatically by LangGraph; persisted to SQLite
# `intent`    — filled by analyze_intent_node; NOT persisted (non-serialisable)
# `body`      — the SearchRequest pydantic model; NOT persisted
# `svc`       — RetrievalService instance; NOT persisted
# `generator` — the SSE generator produced by the chosen node; NOT persisted
#
# LangGraph only checkpoints fields that are JSON-serialisable.  The non-
# serialisable fields (intent, body, svc, generator) are fine because they are
# set fresh on every invocation and never need to be restored from the DB.

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# ── 2. SQLite checkpointer (thread-safe) ─────────────────────────────────────
#
# sqlite3 connections are NOT safe to share across threads.  We use a
# threading.local() so each OS thread gets its own connection.

_run_ctx = threading.local()
_local = threading.local()
_DB_PATH = "papersloth_memory.sqlite"


def _get_saver() -> SqliteSaver:
    """Return a per-thread SqliteSaver, creating it on first access."""
    if not hasattr(_local, "saver"):
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        _local.saver = saver
    return _local.saver


# ── 3. Graph nodes ────────────────────────────────────────────────────────────

def analyze_intent_node(state: AgentState) -> dict:
    intent = classify_with_memory(state["messages"])
    _run_ctx.intent = intent
    return {}   # don't store intent in checkpointed state


def _make_execution_node(handler_fn):
    def node(state: AgentState) -> dict:
        intent = _run_ctx.intent
        body   = _run_ctx.body
        svc    = _run_ctx.svc
        gen = handler_fn(intent, body, svc)
        _run_ctx.generator = gen
        memory_note = AIMessage(
            content=(
                f"[system:executed {intent.type} "
                f"slots={json.dumps(intent.slots)}]"
            )
        )
        return {"messages": [memory_note]}
    return node


# ── 4. Build and compile the graph ───────────────────────────────────────────

def _route_intent(state: AgentState) -> str:
    intent = getattr(_run_ctx, "intent", None)
    valid = {
        "fetch_paper", "topic_search", "tutor_mode",
        "trend_analysis", "general_knowledge", "rag_search",
    }
    intent_type = intent.type if intent else "rag_search"
    return intent_type if intent_type in valid else "rag_search"

def _build_graph() -> StateGraph:
    wf = StateGraph(AgentState)

    wf.add_node("analyze_intent",   analyze_intent_node)
    wf.add_node("fetch_paper",      _make_execution_node(_fetch_paper))
    wf.add_node("topic_search",     _make_execution_node(_topic_search))
    wf.add_node("tutor_mode",       _make_execution_node(_tutor_mode))
    wf.add_node("trend_analysis",   _make_execution_node(_trend_analysis))
    wf.add_node("general_knowledge",_make_execution_node(_general_knowledge))
    wf.add_node("rag_search",       _make_execution_node(_rag_search))

    wf.add_edge(START, "analyze_intent")
    wf.add_conditional_edges("analyze_intent", _route_intent)

    for name in [
        "fetch_paper", "topic_search", "tutor_mode",
        "trend_analysis", "general_knowledge", "rag_search",
    ]:
        wf.add_edge(name, END)

    return wf


# ── 5. Public entry point ─────────────────────────────────────────────────────

def handle(
    query:     str,
    body:      Any,
    svc:       Any,
    thread_id: str,
) -> Generator[str, None, None]:
    config = {"configurable": {"thread_id": thread_id}}

    # Store non-serializable objects in thread-local — never touches the checkpoint
    _run_ctx.body      = body
    _run_ctx.svc       = svc
    _run_ctx.intent    = None
    _run_ctx.generator = None

    initial_state: AgentState = {
        "messages": [HumanMessage(content=query)],
    }

    app = _workflow.compile(checkpointer=_get_saver())
    app.invoke(initial_state, config=config)

    intent = getattr(_run_ctx, "intent", None)
    if intent:
        yield (
            f"data: {json.dumps({'type': 'intent', 'intent': intent.type, 'slots': intent.slots})}\n\n"
        )

    gen = getattr(_run_ctx, "generator", None)
    if gen:
        yield from gen
    else:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Agent produced no output.'})}\n\n"


# ── 6. Handler implementations ────────────────────────────────────────────────

def _general_knowledge(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_flash_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
    )

    sys_msg = SystemMessage(
        content=(
            "You are a helpful university-level engineering tutor. "
            "Answer the student's question clearly and concisely. "
            "Use bullet points or numbered steps where appropriate. "
            "If the question is about a specific exam paper or past year question, "
            "say you need more context instead of guessing."
        )
    )

    yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"

    full_text = ""
    for chunk in llm.stream([sys_msg, HumanMessage(content=body.query)]):
        content = chunk.content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    full_text += block.get("text", "")
                elif isinstance(block, str):
                    full_text += block
        elif isinstance(content, str) and content:
            full_text += content

    CHUNK = 40
    for i in range(0, len(full_text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': full_text[i:i + CHUNK]})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _rag_search(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    filters = svc.build_filter(
        body.course_code,
        body.year,
        body.semester,
        body.question_type,
        body.min_marks,
    )
    yield from svc.stream(body.query, filters, body.top_k, body.rerank_top_n, body.alpha)


def _fetch_paper(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots = intent.slots

    # Prefer explicit body filters; fall back to extracted slots; then regex on query
    course = body.course_code or slots.get("course_code") or _extract_course(body.query)
    year   = body.year        or slots.get("year")
    sem    = body.semester    or slots.get("semester")
    qnum   = slots.get("question_number")

    if not (course and year and sem and qnum):
        missing = []
        if not course: missing.append("subject code")
        if not year:   missing.append("year")
        if not sem:    missing.append("semester")
        if not qnum:   missing.append("question number")
        msg = (
            f"I need {', '.join(missing)} to fetch that directly. "
            "Searching semantically instead…\n\n"
        )
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
        yield from _rag_search(intent, body, svc)
        return

    rows = execute_query(
        """
        SELECT parent_id, question_number, full_text, total_marks, image_urls
        FROM   parent_chunks
        WHERE  course_code = %s AND year = %s AND semester ILIKE %s
               AND question_number = %s
        LIMIT  1
        """,
        (course, year, f"%{sem}%", str(qnum)),
    )

    if not rows:
        msg = f"Q{qnum} not found in {course} {sem} {year}. Searching semantically…\n\n"
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
        yield from _rag_search(intent, body, svc)
        return

    r = rows[0]
    sources = [
        {
            "parent_id":       r[0],
            "question_number": r[1],
            "full_text":       r[2],
            "total_marks":     r[3],
            "image_urls":      r[4] or {},
            "course_code":     course,
            "semester":        sem,
            "year":            year,
        }
    ]
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    answer = f"**Q{qnum} — {course} {sem} {year}** ({r[3]} marks)\n\n{r[2]}"
    CHUNK = 40
    for i in range(0, len(answer), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': answer[i:i + CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _topic_search(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots  = intent.slots
    course = body.course_code or slots.get("course_code") or _extract_course(body.query)
    year   = body.year        or slots.get("year")

    conditions: list[str] = ["1=1"]
    params: list = []
    if course:
        conditions.append("course_code = %s")
        params.append(course)
    if year:
        conditions.append("year = %s")
        params.append(year)

    rows = execute_query(
        f"""
        SELECT question_number,
               COUNT(*) AS times,
               array_agg(DISTINCT semester) AS appearances,
               (array_agg(full_text ORDER BY year DESC, semester DESC))[1] AS sample
        FROM   parent_chunks
        WHERE  {" AND ".join(conditions)}
        GROUP  BY question_number
        ORDER  BY question_number::int
        """,
        params or None,
    )

    if not rows:
        yield f"data: {json.dumps({'type': 'token', 'token': 'No papers found for those filters.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    label = f"{course} " if course else ""
    label += str(year) if year else "all years"

    lines = [f"## Topics in {label}\n\n"]
    for r in rows:
        q, times, appearances, sample = r
        preview  = (sample or "")[:100].replace("\n", " ").strip()
        appeared = ", ".join(str(a) for a in (appearances or [])[:3])
        lines.append(
            f"**Q{q}** — appeared **{times}×** across: {appeared}\n"
            f"> {preview}…\n\n"
        )

    text  = "\n".join(lines)
    CHUNK = 60
    for i in range(0, len(text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i + CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _tutor_mode(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots    = intent.slots
    course   = body.course_code or slots.get("course_code") or _extract_course(body.query)
    year     = body.year        or slots.get("year")
    sem      = body.semester    or slots.get("semester")
    qnum     = slots.get("question_number")
    sub_part = slots.get("sub_part")

    if not (course and year and sem and qnum):
        missing_parts = (
            ("" if course else "- Which subject? (e.g. `RBB3013`)\n")
            + ("" if year   else "- Which year? (e.g. `2025`)\n")
            + ("" if sem    else "- Which semester? (e.g. `May`)\n")
            + ("" if qnum   else "- Which question number? (e.g. `Q2`)\n")
        )
        msg = f"I'd love to help! To pull up the right question, could you tell me:\n\n{missing_parts}"
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    rows = execute_query(
        """
        SELECT full_text, total_marks, children
        FROM   parent_chunks
        WHERE  course_code = %s AND year = %s AND semester ILIKE %s
               AND question_number = %s
        LIMIT  1
        """,
        (course, year, f"%{sem}%", str(qnum)),
    )

    if not rows:
        msg = (
            f"I couldn't find Q{qnum} in {course} {sem} {year}. "
            "Try checking the subject code or semester spelling."
        )
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    full_text, marks, children = rows[0]
    sub_parts = _extract_sub_parts(full_text, children)

    # Emit tutor_start so frontend knows context
    yield (
        f"data: {json.dumps({'type': 'tutor_start', 'question_number': qnum, 'course_code': course, 'year': year, 'semester': sem, 'sub_parts': sub_parts, 'full_text': full_text})}\n\n"
    )

    # Build the prompt for the LLM to actually solve/explain
    if sub_part:
        # Extract the specific sub-part text
        pattern = re.compile(
            rf'\({re.escape(sub_part)}\)(.*?)(?=\s*\([a-z]\)\s|\Z)',
            re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(full_text)
        sub_text = match.group(1).strip() if match else full_text

        user_prompt = (
            f"Here is exam question Q{qnum} from {course} {sem} {year}:\n\n"
            f"{full_text}\n\n"
            f"The student wants help with part ({sub_part}):\n\n"
            f"{sub_text}\n\n"
            f"Please solve and explain part ({sub_part}) step by step. "
            f"Show all working clearly."
        )
    else:
        # Determine what user actually wants — solve all or just orient?
        wants_solution = any(w in body.query.lower() for w in [
            'solve', 'answer', 'explain', 'calculate', 'work through',
            'in order', 'just start', 'start', 'go through', 'all'
        ])

        if wants_solution:
            user_prompt = (
                f"Here is exam question Q{qnum} from {course} {sem} {year} ({marks} marks):\n\n"
                f"{full_text}\n\n"
                f"Please solve and explain ALL parts of this question step by step. "
                f"Label each part clearly (a), (b), (c) etc. Show all working."
            )
        else:
            # Just orient: show parts and ask which to start with
            parts_list = "\n".join(f"- Part **({p})**" for p in sub_parts) if sub_parts else ""
            greeting = (
                f"Sure! Let's work through **Q{qnum}** from {course} {sem} {year} ({marks} marks).\n\n"
            )
            if sub_parts:
                greeting += (
                    f"This question has {len(sub_parts)} parts:\n{parts_list}\n\n"
                    "Which part would you like to start with — or say **'solve all'** to go through them in order?"
                )
            else:
                greeting += f"Here's the question:\n\n> {full_text}\n\nShall I solve it?"
            CHUNK = 40
            for i in range(0, len(greeting), CHUNK):
                yield f"data: {json.dumps({'type': 'token', 'token': greeting[i:i+CHUNK]})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

    # Call LLM to actually solve it
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_flash_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
    )
    sys_msg = SystemMessage(content=(
        "You are a patient, knowledgeable university engineering tutor for UTP students. "
        "When solving exam questions: "
        "(1) Break down each part clearly with its label. "
        "(2) Show all working steps. "
        "(3) State relevant formulas before using them. "
        "(4) Give the final answer clearly. "
        "Use markdown formatting."
    ))

    full_response = ""
    for chunk in llm.stream([sys_msg, HumanMessage(content=user_prompt)]):
        content = chunk.content
        if isinstance(content, list):
            # content is a list of blocks e.g. [{"type": "text", "text": "..."}]
            for block in content:
                if isinstance(block, dict):
                    full_response += block.get("text", "")
                elif isinstance(block, str):
                    full_response += block
        elif isinstance(content, str) and content:
            full_response += content

    CHUNK = 40
    for i in range(0, len(full_response), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': full_response[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _trend_analysis(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots  = intent.slots
    course = body.course_code or slots.get("course_code") or _extract_course(body.query)

    if not course:
        yield f"data: {json.dumps({'type': 'token', 'token': 'Need a subject code to analyse trends. Try filtering by subject first.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    rows = execute_query(
        """
        SELECT question_number,
               COUNT(DISTINCT year)                              AS year_count,
               array_agg(DISTINCT year ORDER BY year DESC)      AS years
        FROM   parent_chunks
        WHERE  course_code = %s
        GROUP  BY question_number
        HAVING COUNT(DISTINCT year) > 1
        ORDER  BY year_count DESC, question_number::int
        LIMIT  10
        """,
        (course,),
    )

    if not rows:
        yield f"data: {json.dumps({'type': 'token', 'token': f'No recurring topics found for {course}.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    lines = [f"### {course} — recurring topics\n\n"]
    for r in rows:
        qnum, ycount, years = r
        lines.append(
            f"**Q{qnum}** appeared in **{ycount}** different years: "
            f"{', '.join(str(y) for y in years)}\n"
        )

    text  = "".join(lines)
    CHUNK = 60
    for i in range(0, len(text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i + CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

_workflow = _build_graph()

# ── 7. Helpers ────────────────────────────────────────────────────────────────

def _extract_sub_parts(full_text: str, children: Any) -> list[str]:
    if children and isinstance(children, list) and len(children) > 1:
        return [str(chr(97 + i)) for i in range(len(children))]
    # Only match (a), (b), (c) style — NOT (1), (2), (3)
    parts = re.findall(r'\(([a-z])\)', full_text[:800])
    seen: set = set()
    unique: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique or []


def _extract_course(query: str) -> Optional[str]:
    """
    Try to infer a course code from free text.
    1. Pattern match e.g. "UPCE3273"
    2. Fuzzy search exam_papers.subject_name
    """
    m = re.search(r"\b([A-Z]{2,4}\d{4})\b", query, re.I)
    if m:
        return m.group(1).upper()

    keywords = [
        w for w in re.findall(r"\b[a-zA-Z]{4,}\b", query)
        if w.lower() not in {
            "give", "show", "what", "from", "help", "with",
            "that", "came", "topics", "question", "paper", "find",
        }
    ][:3]

    if not keywords:
        return None

    conditions = " AND ".join("subject_name ILIKE %s" for _ in keywords)
    row = execute_query(
        f"SELECT course_code FROM exam_papers WHERE {conditions} LIMIT 1",
        [f"%{k}%" for k in keywords],
        fetch="one",
    )
    return row[0] if row else None