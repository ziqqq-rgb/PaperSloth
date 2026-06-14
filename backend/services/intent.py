"""
services/intent.py
──────────────────
Intent classification for the PaperSloth agent.

Exports
───────
classify(query)                    → Intent   (stateless, single-turn)
classify_with_memory(messages)     → Intent   (multi-turn, uses chat history)
Intent                             dataclass
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List

from langchain_core.messages import AnyMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from core.config import settings


# ── 1. Pydantic schemas (structured output) ───────────────────────────────────

class IntentSlots(BaseModel):
    course_code:     Optional[str] = Field(default=None)
    year:            Optional[int] = Field(default=None)
    semester:        Optional[str] = Field(default=None)
    question_number: Optional[str] = Field(default=None)
    sub_part:        Optional[str] = Field(default=None)


class IntentResult(BaseModel):
    type: str = Field(
        description=(
            "One of: fetch_paper, topic_search, tutor_mode, "
            "trend_analysis, general_knowledge, rag_search"
        )
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    slots: IntentSlots


# ── 2. Public dataclass returned to callers ───────────────────────────────────

@dataclass
class Intent:
    type:       str
    confidence: float
    slots:      dict = field(default_factory=dict)


# ── 3. Regex fast-path patterns ───────────────────────────────────────────────

_FETCH = re.compile(
    r'\b(give me|show me|get|fetch|display)\b.{0,40}\b(q\d+|question \d+)\b', re.I
)
_TUTOR = re.compile(
    r'\b(help me with|explain|walk me through|how do i)\b.{0,60}\b(q\d+|question \d+)\b',
    re.I,
)
_TREND = re.compile(
    r'\b(trend|recurring|repeat|common|frequent|most asked|appear most'
    r'|rare|least common|uncommon|infrequent|only once|never repeat)\b',
    re.I,
)
# NOTE: _TOPIC matches requests to BROWSE/LIST all questions in a course/year —
# no topic/subject filter implied. A query that names a specific subject or
# concept (e.g. "questions related to X", "question about Y") is a rag_search,
# even if it contains the word "question(s)". 
_TOPIC = re.compile(
    r'\b(topic|what questions|list questions|all questions)\b', re.I
)
# If the query matches _TOPIC but ALSO contains a subject/topic-filter phrase
# ("related to", "about", "on the topic of", "regarding", "concerning"), it's
# actually a content search (rag_search), not a browse/list request.
_TOPIC_SUBJECT_GUARD = re.compile(
    r'\b(related to|about|on the topic of|regarding|concerning|on)\b', re.I
)
_GENERAL = re.compile(
    r'\b(what is|explain|define|how does|why does|what are)\b', re.I
)

_QNUM = re.compile(r'\b(?:q(?:uestion\s*)?(\d+)([a-z])?)\b', re.I)
_YEAR = re.compile(r'\b(20\d{2})\b')
_SEM  = re.compile(r'\b(january|may|august|september)\b', re.I)


def _is_topic_browse(text: str) -> bool:
    """
    True only if the query is a genuine browse/list request
    (e.g. "what questions are in RBB3013 2025", "list all questions"),
    and NOT a topic/subject-filtered content search
    (e.g. "give me questions related to gradient descent").
    """
    return bool(_TOPIC.search(text)) and not _TOPIC_SUBJECT_GUARD.search(text)


# ── 4. Regex slot extractor (shared) ─────────────────────────────────────────

def _extract_slots(text: str) -> dict:
    slots: dict = {}
    if m := _QNUM.search(text):
        slots["question_number"] = m.group(1)          
        if m.group(2):
            slots["sub_part"] = m.group(2).lower()    
    if m := _YEAR.search(text):
        slots["year"] = int(m.group())
    if m := _SEM.search(text):
        slots["semester"] = m.group().capitalize()
    return slots


# ── 5. LLM classifier (lazy, thread-safe via function scope) ──────────────────

def _build_llm_classifier():
    """Builds a fresh structured-output chain. Called lazily."""
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_flash_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )
    return llm.with_structured_output(IntentResult)


_classifier_cache: dict = {}   # module-level cache, safe for single-process uvicorn


def _get_llm_classifier():
    if "chain" not in _classifier_cache:
        _classifier_cache["chain"] = _build_llm_classifier()
    return _classifier_cache["chain"]


# ── 6. Single-turn classify (stateless) ──────────────────────────────────────

def classify(query: str) -> Intent:
    """
    Fast single-turn intent classifier.
    Uses regex fast-path; falls back to LLM for ambiguous queries.
    This is the function imported by the legacy search.py agent endpoint.
    """
    slots = _extract_slots(query)

    # Regex fast-paths (ordered most-specific → least-specific)
    if _TUTOR.search(query):
        return Intent("tutor_mode", 0.9, slots)
    if _FETCH.search(query):
        return Intent("fetch_paper", 0.9, slots)
    if _TREND.search(query):
        return Intent("trend_analysis", 0.85, slots)
    if _is_topic_browse(query):
        return Intent("topic_search", 0.85, slots)

    # LLM fallback for the single-turn case
    try:
        result: IntentResult = _get_llm_classifier().invoke(query)
        merged_slots = {**result.slots.model_dump(exclude_none=True), **slots}
        return Intent(result.type, result.confidence, merged_slots)
    except Exception:
        return Intent("rag_search", 0.5, slots)


# ── 7. Multi-turn classify (memory-aware) ────────────────────────────────────

_MEMORY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are the intent router for the PaperSloth university exam assistant. "
        "Analyse the user's latest query in the context of the full conversation history. "
        "CRITICAL RULES:\n"
        "1. If the user asks a follow-up (e.g. 'what about part b?', 'help me with 2a', 'and Q3?'), "
        "you MUST inherit course_code, year, semester, and question_number from "
        "previous messages where they were stated.\n"
        "2. question_number is ONLY the digit (e.g. '2' not '2a'). Sub-part letters (a/b/c) go in sub_part.\n"
        "3. Prefer tutor_mode when the user wants step-by-step help with a specific question.\n"
        "4. Use trend_analysis for any question about which topics are common, frequent, recurring, "
        "rare, uncommon, or infrequent across past papers.\n"
        "5. topic_search is ONLY for browsing/listing ALL questions in a course and/or year with "
        "NO subject-matter filter (e.g. 'what questions are in RBB3013 2025', 'list all questions "
        "for this course'). It returns every question regardless of content.\n"
        "6. If the user names a SPECIFIC SUBJECT, TOPIC, or CONCEPT — even phrased as 'question(s) "
        "about X', 'question related to X', 'find questions on X' — this is rag_search, NOT "
        "topic_search. rag_search performs a semantic content search and will correctly report "
        "'no relevant questions found' if the topic isn't covered by any past paper. Never route a "
        "topic-filtered request to topic_search, because topic_search ignores the topic filter "
        "entirely and will dump unrelated questions.\n"
        "7. Use rag_search as the default when nothing else fits.\n"
        "Return structured JSON only."
        "8. If the user's message contains an inline question (e.g. 'help me answer: Consider the matrix...'), "
        "route to general_knowledge — the question text is self-contained and needs no DB lookup.\n"
    ),
    MessagesPlaceholder(variable_name="messages"),
])

def classify_with_memory(messages: List[AnyMessage]) -> Intent:
    """
    Memory-aware intent classifier for use inside the LangGraph agent.
    Receives the full message history (from SQLite checkpointer) and returns
    an Intent that may inherit slots from previous turns.
    """
    latest_query = messages[-1].content.strip()
    slots = _extract_slots(latest_query)

    # For a brand-new conversation (single message) the regex fast-path is enough
    if len(messages) == 1:
        if _TUTOR.search(latest_query):
            return Intent("tutor_mode", 0.9, slots)
        if _FETCH.search(latest_query):
            return Intent("fetch_paper", 0.9, slots)
        if _TREND.search(latest_query):
            return Intent("trend_analysis", 0.85, slots)
        if _is_topic_browse(latest_query):
            return Intent("topic_search", 0.85, slots)

    # Multi-turn: send full history to the LLM so it can inherit context
    chain = _MEMORY_PROMPT | _get_llm_classifier()
    try:
        result: IntentResult = chain.invoke({"messages": messages})
        # Regex slots take precedence (they are unambiguous)
        merged_slots = {**result.slots.model_dump(exclude_none=True), **slots}
        return Intent(result.type, result.confidence, merged_slots)
    except Exception:
        return Intent("rag_search", 0.5, slots)