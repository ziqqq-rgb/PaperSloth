import json
import re
import sqlite3
from typing import Generator, TypedDict, Any, Callable, Annotated

# ── LangGraph & LangChain Imports ─────────────────────────────────────────────
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from core.database import execute_query
from core.config import settings

# This imports the new memory-aware router we built in intent.py
from intent import classify_with_memory 

# ── 1. LangGraph State with Memory ───────────────────────────────────────────

class AgentState(TypedDict):
    # LangGraph natively appends new messages to this list from the database
    messages: Annotated[list[AnyMessage], add_messages]
    intent: Any
    body: Any
    svc: Any
    generator: Any  # Stores the resulting SSE generator for FastAPI to stream

# ── 2. Memory Wrapper Trick ──────────────────────────────────────────────────

def create_node(handler_func: Callable, node_name: str):
    """Wraps SSE generators and injects an automated memory log into SQLite."""
    def node(state: AgentState):
        gen = handler_func(state["intent"], state["body"], state["svc"])
        
        # Save a "silent" message to the DB so the intent router knows 
        # exactly what context the agent was handling in the next turn!
        slots_str = str(state['intent'].slots) if state.get('intent') else "{}"
        memory_log = AIMessage(
            content=f"[System State: Executed '{node_name}' with context: {slots_str}]"
        )
        return {"generator": gen, "messages": [memory_log]}
    return node

# ── 3. Graph Nodes (Routing) ─────────────────────────────────────────────────

def analyze_intent_node(state: AgentState):
    """Node 1: Looks at history and figures out the user's intent."""
    intent = classify_with_memory(state["messages"])
    return {"intent": intent}

def route_intent(state: AgentState) -> str:
    """Conditional edge routing based on the classifier's intent."""
    valid_nodes = [
        "fetch_paper", "topic_search", "tutor_mode", 
        "trend_analysis", "general_knowledge"
    ]
    if state["intent"].type in valid_nodes:
        return state["intent"].type
    return "rag_search"

# ── 4. Build & Compile Graph with SQLite ─────────────────────────────────────

workflow = StateGraph(AgentState)

# Start by checking intent
workflow.add_node("analyze_intent", analyze_intent_node)

# Add all execution nodes
workflow.add_node("fetch_paper", create_node(lambda i, b, s: _fetch_paper(i, b, s), "fetch_paper"))
workflow.add_node("topic_search", create_node(lambda i, b, s: _topic_search(i, b, s), "topic_search"))
workflow.add_node("tutor_mode", create_node(lambda i, b, s: _tutor_mode(i, b, s), "tutor_mode"))
workflow.add_node("trend_analysis", create_node(lambda i, b, s: _trend_analysis(i, b, s), "trend_analysis"))
workflow.add_node("general_knowledge", create_node(lambda i, b, s: _general_knowledge(i, b, s), "general_knowledge"))
workflow.add_node("rag_search", create_node(lambda i, b, s: _rag_search(i, b, s), "rag_search"))

workflow.add_edge(START, "analyze_intent")
workflow.add_conditional_edges("analyze_intent", route_intent)

for node_name in ["fetch_paper", "topic_search", "tutor_mode", "trend_analysis", "general_knowledge", "rag_search"]:
    workflow.add_edge(node_name, END)

# Attach local SQLite Database Checkpointer
conn = sqlite3.connect("papersloth_memory.sqlite", check_same_thread=False)
memory_saver = SqliteSaver(conn)
memory_saver.setup()

# Compile
agent_app = workflow.compile(checkpointer=memory_saver)

# ── 5. FastAPI Entry Point ───────────────────────────────────────────────────

def handle(query: str, body: Any, svc: Any, thread_id: str) -> Generator[str, None, None]:
    """
    Entry point from FastAPI.
    Requires thread_id to be passed from the FastAPI router to track sessions.
    """
    # Pass the thread_id so SQLite knows which student's history to load
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        # Appends the newest message to the SQLite DB automatically
        "messages": [HumanMessage(content=query)],
        "body": body,
        "svc": svc,
        "generator": None
    }
    
    final_state = agent_app.invoke(initial_state, config=config)
    
    if final_state.get("generator"):
        yield from final_state["generator"]
    else:
        yield from _rag_search(final_state["intent"], body, svc)


# ── 6. Node Implementations ──────────────────────────────────────────────────

def _general_knowledge(intent, body, svc):
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_flash_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.1
    )

    sys_msg = SystemMessage(content=(
        "You are a helpful university-level engineering tutor. "
        "Answer the student's question clearly and concisely. "
        "Use bullet points or numbered steps where appropriate. "
        "If the question is about a specific exam paper or past year question, "
        "say you need more context instead of guessing."
    ))

    yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"

    full_text = ""
    for chunk in llm.stream([sys_msg, HumanMessage(content=body.query)]):
        if chunk.content:
            full_text += chunk.content

    CHUNK = 40
    for i in range(0, len(full_text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': full_text[i:i+CHUNK]})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _rag_search(intent, body, svc):
    filters = svc.build_filter(
        body.course_code, body.year, body.semester,
        body.question_type, body.min_marks,
    )
    yield from svc.stream(body.query, filters, body.top_k, body.rerank_top_n, body.alpha)


def _fetch_paper(intent, body, svc):
    slots = intent.slots
    qnum  = slots.get('question_number') or body.query  

    # Added slots.get() check to ensure memory carries over correctly!
    course = body.course_code or _extract_course(body.query) or slots.get('course_code')
    year   = body.year   or slots.get('year')
    sem    = body.semester or slots.get('semester')

    if not (course and year and sem):
        yield f"data: {json.dumps({'type': 'token', 'token': 'I need the subject code, year, and semester to fetch that directly. Searching semantically instead…\n\n'})}\n\n"
        yield from _rag_search(intent, body, svc)
        return

    rows = execute_query("""
        SELECT parent_id, question_number, full_text, total_marks, image_urls
        FROM   parent_chunks
        WHERE  course_code = %s AND year = %s AND semester ILIKE %s
            AND  question_number = %s
        LIMIT 1
    """, (course, year, f"%{sem}%", str(qnum)))

    if not rows:
        yield f"data: {json.dumps({'type': 'token', 'token': f'Q{qnum} not found in {course} {sem} {year}. Searching semantically…\n\n'})}\n\n"
        yield from _rag_search(intent, body, svc)
        return

    r = rows[0]
    sources = [{
        "parent_id":       r[0],
        "question_number": r[1],
        "full_text":       r[2],
        "total_marks":     r[3],
        "image_urls":      r[4] or {},
        "course_code":     course,
        "semester":        sem,
        "year":            year,
    }]
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'token': f'**Q{qnum} — {course} {sem} {year}** ({r[3]} marks)\n\n{r[2]}'})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _topic_search(intent, body, svc):
    slots = intent.slots
    course = body.course_code or _extract_course(body.query) or slots.get('course_code')
    year   = body.year or slots.get('year')

    conditions = ["1=1"]
    params = []
    if course:
        conditions.append("course_code = %s"); params.append(course)
    if year:
        conditions.append("year = %s"); params.append(year)

    rows = execute_query(f"""
        SELECT question_number,
            COUNT(*)                                                     AS times,
            array_agg(DISTINCT semester)                                 AS appearances,
            (array_agg(full_text ORDER BY year DESC, semester DESC))[1]  AS sample
        FROM   parent_chunks
        WHERE  {" AND ".join(conditions)}
        GROUP  BY question_number
        ORDER  BY question_number::int
    """, params or None)

    if not rows:
        yield f"data: {json.dumps({'type': 'token', 'token': 'No papers found for those filters.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    label = f"{course} " if course else ""
    label += f"{year}" if year else "all years"

    lines = [f"## Topics in {label}\n\n"]
    for r in rows:
        q, times, appearances, sample = r
        preview = (sample or '')[:100].replace('\n', ' ').strip()
        appeared = ', '.join(str(a) for a in (appearances or [])[:3])
        lines.append(
            f"**Q{q}** — appeared **{times}×** across: {appeared}\n"
            f"> {preview}…\n\n"
        )

    text = '\n'.join(lines)
    CHUNK = 60
    for i in range(0, len(text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _tutor_mode(intent, body, svc):
    slots  = intent.slots
    course = body.course_code or _extract_course(body.query) or slots.get('course_code')
    year   = body.year   or slots.get('year')
    sem    = body.semester or slots.get('semester')
    qnum   = slots.get('question_number')

    if not (course and year and sem and qnum):
        msg = (
            "I'd love to help! To pull up the right question, could you tell me:\n\n"
            + ("" if course else "- Which subject? (e.g. `UPCE3273`)\n")
            + ("" if year   else "- Which year? (e.g. `2025`)\n")
            + ("" if sem    else "- Which semester? (e.g. `May`)\n")
            + ("" if qnum   else "- Which question number? (e.g. `Q2`)\n")
        )
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    rows = execute_query("""
        SELECT full_text, total_marks, children
        FROM   parent_chunks
        WHERE  course_code = %s AND year = %s AND semester ILIKE %s
            AND  question_number = %s
        LIMIT 1
    """, (course, year, f"%{sem}%", str(qnum)))

    if not rows:
        msg = f"I couldn't find Q{qnum} in {course} {sem} {year}. Try checking the subject code or semester spelling."
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    full_text, marks, children = rows[0]

    sub_parts = _extract_sub_parts(full_text, children)
    parts_list = '\n'.join([f"- Part **({p})**" for p in sub_parts]) if sub_parts else ""

    greeting = (
        f"Sure! Let's work through **Q{qnum}** from {course} {sem} {year} ({marks} marks).\n\n"
        f"This question has {len(sub_parts)} part{'s' if len(sub_parts) != 1 else ''}:\n"
        f"{parts_list}\n\n"
        f"Which part would you like to start with — or shall we go through them in order?"
    )

    yield f"data: {json.dumps({'type': 'tutor_start', 'question_number': qnum, 'course_code': course, 'year': year, 'semester': sem, 'sub_parts': sub_parts, 'full_text': full_text})}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'token': greeting})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _trend_analysis(intent, body, svc):
    slots = intent.slots
    course = body.course_code or _extract_course(body.query) or slots.get('course_code')

    rows = execute_query("""
        SELECT question_number,
               COUNT(DISTINCT year)  AS year_count,
               array_agg(DISTINCT year ORDER BY year DESC) AS years
        FROM   parent_chunks
        WHERE  course_code = %s
        GROUP  BY question_number
        HAVING COUNT(DISTINCT year) > 1
        ORDER  BY year_count DESC, question_number::int
        LIMIT 10
    """, (course,)) if course else []

    if not rows:
        yield f"data: {json.dumps({'type': 'token', 'token': 'Need a subject code to analyse trends. Try filtering by subject first.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    lines = [f"### {course} — recurring topics\n\n"]
    for r in rows:
        qnum, ycount, years = r
        lines.append(f"**Q{qnum}** appeared in {ycount} different years: {', '.join(str(y) for y in years)}\n")

    text = ''.join(lines)
    CHUNK = 60
    for i in range(0, len(text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_sub_parts(full_text: str, children) -> list[str]:
    if children and isinstance(children, list) and len(children) > 1:
        return [str(i+1) for i in range(len(children))]
    parts = re.findall(r'\(([a-z]+)\)', full_text[:800])
    seen, unique = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique or ['a']  

def _extract_course(query: str) -> str | None:
    m = re.search(r'\b([A-Z]{2,4}\d{4})\b', query, re.I)
    if m:
        return m.group(1).upper()

    keywords = re.findall(r'\b[a-zA-Z]{4,}\b', query) 
    if not keywords:
        return None

    search_terms = [k for k in keywords if k.lower() not in
                    ('give', 'show', 'what', 'from', 'help', 'with',
                     'that', 'came', 'topics', 'question', 'paper')][:3]
    if not search_terms:
        return None

    conditions = " AND ".join([f"subject_name ILIKE %s" for _ in search_terms])
    params = [f"%{t}%" for t in search_terms]

    row = execute_query(f"""
        SELECT course_code FROM exam_papers
        WHERE {conditions}
        LIMIT 1
    """, params, fetch="one")

    return row[0] if row else None