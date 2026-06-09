"""
services/agent/handlers.py
──────────────────────────
One function per intent, each returning a Generator[str, None, None]
that yields SSE-formatted strings.

Handlers are stateless — they receive (intent, body, svc) and yield events.
The agent graph in graph.py calls them via _make_execution_node.
"""

import json
import re
from typing import Any, Generator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from core.config import settings
from core.database import execute_query
from services.intent import Intent
from services.agent.helpers import extract_course, extract_sub_parts


# ── general_knowledge ─────────────────────────────────────────────────────────

def general_knowledge(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
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
        yield f"data: {json.dumps({'type': 'token', 'token': full_text[i:i+CHUNK]})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── rag_search ────────────────────────────────────────────────────────────────

def rag_search(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    filters = svc.build_filter(
        body.course_code,
        body.year,
        body.semester,
        body.question_type,
        body.min_marks,
    )
    yield from svc.stream(body.query, filters, body.top_k, body.rerank_top_n, body.alpha)


# ── fetch_paper ───────────────────────────────────────────────────────────────

def fetch_paper(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots  = intent.slots
    course = body.course_code or slots.get("course_code") or extract_course(body.query)
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
        yield from rag_search(intent, body, svc)
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
        yield from rag_search(intent, body, svc)
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

    answer = f"**Q{qnum} — {course} {sem} {year}** ({r[3]} marks)\n\n{r[2]}"
    CHUNK = 40
    for i in range(0, len(answer), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': answer[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── topic_search ──────────────────────────────────────────────────────────────

def topic_search(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots  = intent.slots
    course = body.course_code or slots.get("course_code") or extract_course(body.query)
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
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── tutor_mode ────────────────────────────────────────────────────────────────

def tutor_mode(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots    = intent.slots
    course   = body.course_code or slots.get("course_code") or extract_course(body.query)
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
    sub_parts = extract_sub_parts(full_text, children)

    yield (
        f"data: {json.dumps({'type': 'tutor_start', 'question_number': qnum, 'course_code': course, 'year': year, 'semester': sem, 'sub_parts': sub_parts, 'full_text': full_text})}\n\n"
    )

    if sub_part:
        pattern = re.compile(
            rf'\({re.escape(sub_part)}\)(.*?)(?=\s*\([a-z]\)\s|\Z)',
            re.DOTALL | re.IGNORECASE,
        )
        match    = pattern.search(full_text)
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
        wants_solution = any(w in body.query.lower() for w in [
            "solve", "answer", "explain", "calculate", "work through",
            "in order", "just start", "start", "go through", "all",
        ])

        if wants_solution:
            user_prompt = (
                f"Here is exam question Q{qnum} from {course} {sem} {year} ({marks} marks):\n\n"
                f"{full_text}\n\n"
                f"Please solve and explain ALL parts of this question step by step. "
                f"Label each part clearly (a), (b), (c) etc. Show all working."
            )
        else:
            parts_list = "\n".join(f"- Part **({p})**" for p in sub_parts) if sub_parts else ""
            greeting   = f"Sure! Let's work through **Q{qnum}** from {course} {sem} {year} ({marks} marks).\n\n"
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


# ── trend_analysis ────────────────────────────────────────────────────────────

def trend_analysis(intent: Intent, body: Any, svc: Any) -> Generator[str, None, None]:
    slots  = intent.slots
    course = body.course_code or slots.get("course_code") or extract_course(body.query)

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
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"