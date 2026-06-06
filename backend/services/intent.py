import json
import google.generativeai as genai
from core.config import settings
import re
from dataclasses import dataclass

_flash = None

def _get_flash():
    global _flash
    if _flash is None:
        genai.configure(api_key=settings.gemini_api_key)
        _flash = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=(
                "You are an intent classifier for a university exam assistant. "
                "Classify the user query into exactly one of these intents: "
                "fetch_paper, topic_search, tutor_mode, trend_analysis, rag_search. "
                "Also extract any slots: course_code, year, semester, question_number. "
                "Respond ONLY with valid JSON. No explanation."
            )
        )
    return _flash


def _llm_classify(query: str) -> dict:
    """Fallback LLM classifier for ambiguous queries."""
    resp = _get_flash().generate_content(
        f"Classify this query: {query}\n\n"
        'Respond with JSON: {"intent": "...", "slots": {"course_code": null, "year": null, "semester": null, "question_number": null}}'
    )
    try:
        text = resp.text.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(text)
    except Exception:
        return {"intent": "rag_search", "slots": {}}
    

@dataclass
class Intent:
    type: str
    confidence: float
    slots: dict

_FETCH = re.compile(
    r'\b(give me|show me|get|fetch|display)\b.{0,40}\b(q\d+|question \d+)\b', re.I
)
_TUTOR = re.compile(
    r'\b(help me with|explain|walk me through|i don.t understand|how do i|can you help)\b.{0,60}\b(q\d+|question \d+)\b', re.I
)
_TOPIC = re.compile(
    r'\b(what topics|which topics|topics that came out|topics covered|what (came|comes) out)\b', re.I
)
_TREND = re.compile(
    r'\b(trend|pattern|most common|frequently|how often|over the years)\b', re.I
)
_QNUM = re.compile(r'\b(q\d+|question\s*(\d+))\b', re.I)
_YEAR = re.compile(r'\b(20\d{2})\b')
_SEM  = re.compile(r'\b(january|may|august|september)\b', re.I)

def classify(query: str) -> Intent:
    q = query.strip()
    slots = {}

    if m := _QNUM.search(q):
        slots['question_number'] = re.search(r'\d+', m.group()).group()
    if m := _YEAR.search(q):
        slots['year'] = int(m.group())
    if m := _SEM.search(q):
        slots['semester'] = m.group().capitalize()

    if _TUTOR.search(q):
        return Intent('tutor_mode',    0.9, slots)
    if _FETCH.search(q):
        return Intent('fetch_paper',   0.9, slots)
    if _TOPIC.search(q):
        return Intent('topic_search',  0.9, slots)
    if _TREND.search(q):
        return Intent('trend_analysis',0.85, slots)

    return Intent('rag_search', 0.7, slots)
