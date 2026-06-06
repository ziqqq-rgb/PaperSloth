import json
from typing import Generator
from core.database import execute_query

TUTOR_SYSTEM = (
    "You are a Socratic tutor helping a university student work through an exam question. "
    "Never give the full answer directly. Instead: "
    "1. Ask what the student already knows about the concept. "
    "2. Give a hint that points toward the method, not the answer. "
    "3. If they're stuck after 2 hints, reveal the approach step-by-step. "
    "Keep responses concise — 3-5 sentences max per turn."
)


def handle(intent, body, svc) -> Generator[str, None, None]:
    dispatch = {
        'fetch_paper':    _fetch_paper,
        'topic_search':   _topic_search,
        'tutor_mode':     _tutor_mode,
        'trend_analysis': _trend_analysis,
        'rag_search':     _rag_search,
    }
    handler = dispatch.get(intent.type, _rag_search)
    yield from handler(intent, body, svc)


def _rag_search(intent, body, svc):
    """Existing pipeline — no change."""
    filters = svc.build_filter(
        body.course_code, body.year, body.semester,
        body.question_type, body.min_marks,
    )
    yield from svc.stream(body.query, filters, body.top_k, body.rerank_top_n, body.alpha)


def _fetch_paper(intent, body, svc):
    """
    Student asked for a specific question. Fetch it directly from Postgres
    instead of going through RAG — exact match is better than semantic search here.
    """
    slots = intent.slots
    qnum  = slots.get('question_number') or body.query  # fallback

    course = body.course_code or _extract_course(body.query)
    year   = body.year   or slots.get('year')
    sem    = body.semester or slots.get('semester')

    if not (course and year and sem):
        # Not enough info — fall back to RAG with a note
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
    """
    Aggregate topics via SQL — don't use RAG.
    Groups by question number, counts appearances.
    """
    course = body.course_code or _extract_course(body.query)
    year   = body.year or intent.slots.get('year')

    conditions = ["1=1"]
    params = []
    if course:
        conditions.append("course_code = %s"); params.append(course)
    if year:
        conditions.append("year = %s"); params.append(year)

    rows = execute_query(f"""
        SELECT question_number,
            COUNT(*)                                                              AS times,
            array_agg(DISTINCT semester)                                     AS appearances,
            (array_agg(full_text ORDER BY year DESC, semester DESC))[1]          AS sample
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
            # Show max 3 semesters, cleaned up
        appeared = ', '.join(str(a) for a in (appearances or [])[:3])
        lines.append(
            f"**Q{q}** — appeared **{times}×** across: {appeared}\n"
            f"> {preview}…\n\n"
        )

    text = '\n'.join(lines)
    # Stream in chunks so it feels live
    CHUNK = 60
    for i in range(0, len(text), CHUNK):
        import time
        yield f"data: {json.dumps({'type': 'token', 'token': text[i:i+CHUNK]})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _tutor_mode(intent, body, svc):
    """
    Student wants help with a question, not just to see it.
    First turn: fetch the question, then ask which sub-part to start with.
    The frontend tracks tutor state and sends follow-up turns back here.
    """
    slots  = intent.slots
    course = body.course_code or _extract_course(body.query)
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
        # Added opening " for the f-string, escaped quotes for JSON keys, and fixed syntax
        msg = f"I couldn't find Q{qnum} in {course} {sem} {year}. Try checking the subject code or semester spelling."
        yield f"data: {json.dumps({'type': 'token', 'token': msg})}\n\n"        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return


    full_text, marks, children = rows[0]

    # Parse sub-parts from children or from the question text
    sub_parts = _extract_sub_parts(full_text, children)
    parts_list = '\n'.join([f"- Part **({p})**" for p in sub_parts]) if sub_parts else ""

    greeting = (
        f"Sure! Let's work through **Q{qnum}** from {course} {sem} {year} ({marks} marks).\n\n"
        f"This question has {len(sub_parts)} part{'s' if len(sub_parts) != 1 else ''}:\n"
        f"{parts_list}\n\n"
        f"Which part would you like to start with — or shall we go through them in order?"
    )

    # Emit a special tutor_start event so the frontend can track state
    yield f"data: {json.dumps({'type': 'tutor_start', 'question_number': qnum, 'course_code': course, 'year': year, 'semester': sem, 'sub_parts': sub_parts, 'full_text': full_text})}\n\n"
    yield f"data: {json.dumps({'type': 'token', 'token': greeting})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


def _trend_analysis(intent, body, svc):
    """SQL-based trend: which topics appear most across years."""
    course = body.course_code or _extract_course(body.query)

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

def _extract_course(query: str) -> str | None:
    """Pull a UTP course code like UPCE3273 or ICB3813 from the query."""
    import re
    m = re.search(r'\b([A-Z]{2,4}\d{4})\b', query, re.I)
    return m.group(1).upper() if m else None


def _extract_sub_parts(full_text: str, children) -> list[str]:
    """Extract sub-part labels (a, b, c, i, ii, iii) from question text."""
    import re
    if children and isinstance(children, list) and len(children) > 1:
        return [str(i+1) for i in range(len(children))]
    # Regex fallback: look for (a), (b), (i), (ii) patterns
    parts = re.findall(r'\(([a-z]+)\)', full_text[:800])
    seen, unique = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique or ['a']  

def _extract_course(query: str) -> str | None:
    """
    First try regex for explicit course codes like UPCE3273.
    Then try a DB lookup for subject name keywords.
    """
    import re
    # Try explicit code first
    m = re.search(r'\b([A-Z]{2,4}\d{4})\b', query, re.I)
    if m:
        return m.group(1).upper()

    # Try subject name keyword match against DB
    keywords = re.findall(r'\b[a-zA-Z]{4,}\b', query)  # words 4+ chars
    if not keywords:
        return None

    # Build a ILIKE search across subject_name in exam_papers
    # Use first 3 meaningful words to avoid noise
    search_terms = [k for k in keywords if k.lower() not in
                    ('give', 'show', 'what', 'from', 'help', 'with',
                     'that', 'came', 'topics', 'question', 'paper')][:3]
    if not search_terms:
        return None

    from core.database import execute_query
    conditions = " AND ".join([f"subject_name ILIKE %s" for _ in search_terms])
    params = [f"%{t}%" for t in search_terms]

    row = execute_query(f"""
        SELECT course_code FROM exam_papers
        WHERE {conditions}
        LIMIT 1
    """, params, fetch="one")

    return row[0] if row else None

def handle(intent, body, svc) -> Generator[str, None, None]:
    dispatch = {
        'fetch_paper':       _fetch_paper,
        'topic_search':      _topic_search,
        'tutor_mode':        _tutor_mode,
        'trend_analysis':    _trend_analysis,
        'general_knowledge': _general_knowledge,  # ← new
        'rag_search':        _rag_search,
    }
    handler = dispatch.get(intent.type, _rag_search)
    yield from handler(intent, body, svc)


def _general_knowledge(intent, body, svc):
    """
    Pure Gemini answer — no RAG, no Pinecone, no DB.
    For conceptual/theory questions the model already knows.
    """
    import google.generativeai as genai
    from core.config import settings

    model = genai.GenerativeModel(
        settings.gemini_flash_model,   # use flash — fast, cheap, good enough for theory
        system_instruction=(
            "You are a helpful university-level engineering tutor. "
            "Answer the student's question clearly and concisely. "
            "Use bullet points or numbered steps where appropriate. "
            "If the question is about a specific exam paper or past year question, "
            "say you need more context instead of guessing."
        )
    )

    # Emit empty sources so frontend knows there are none
    yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"

    full_text = ""
    for chunk in model.generate_content(body.query, stream=True):
        if chunk.text:
            full_text += chunk.text

    CHUNK = 40
    for i in range(0, len(full_text), CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': full_text[i:i+CHUNK]})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"