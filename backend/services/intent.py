import re
from dataclasses import dataclass
from typing import Optional, List

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AnyMessage
from core.config import settings

# ── 1. Pydantic Schemas ───────────────────────────────────────────────────────
class IntentSlots(BaseModel):
    course_code: Optional[str] = Field(default=None)
    year: Optional[int] = Field(default=None)
    semester: Optional[str] = Field(default=None)
    question_number: Optional[str] = Field(default=None)

class IntentResult(BaseModel):
    type: str = Field(description="fetch_paper, topic_search, tutor_mode, trend_analysis, general_knowledge, rag_search")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    slots: IntentSlots

@dataclass
class Intent:
    type: str
    confidence: float
    slots: dict

# ── 2. LangChain LLM Setup ────────────────────────────────────────────────────
_llm_classifier = None

def _get_llm_classifier():
    global _llm_classifier
    if _llm_classifier is None:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_flash_model,
            google_api_key=settings.gemini_api_key,
            temperature=0
        )
        _llm_classifier = llm.with_structured_output(IntentResult)
    return _llm_classifier

# ── 3. Regex Patterns (Unchanged) ─────────────────────────────────────────────
_FETCH = re.compile(r'\b(give me|show me|get|fetch|display)\b.{0,40}\b(q\d+|question \d+)\b', re.I)
_TUTOR = re.compile(r'\b(help me with|explain|walk me through|how do i)\b.{0,60}\b(q\d+|question \d+)\b', re.I)
_QNUM = re.compile(r'\b(q\d+|question\s*(\d+))\b', re.I)
_YEAR = re.compile(r'\b(20\d{2})\b')
_SEM  = re.compile(r'\b(january|may|august|september)\b', re.I)

# ── 4. Memory-Aware Router ────────────────────────────────────────────────────
def classify_with_memory(messages: List[AnyMessage]) -> Intent:
    """Evaluates intent using both the latest query and full SQLite chat history."""
    
    # Extract the exact text of the user's latest message
    latest_query = messages[-1].content.strip()
    slots = {}

    if m := _QNUM.search(latest_query): slots['question_number'] = re.search(r'\d+', m.group()).group()
    if m := _YEAR.search(latest_query): slots['year'] = int(m.group())
    if m := _SEM.search(latest_query): slots['semester'] = m.group().capitalize()

    # If it's a brand new chat (no history) AND regex finds everything we need, return fast!
    if len(messages) == 1:
        if _TUTOR.search(latest_query): return Intent('tutor_mode', 0.9, slots)
        if _FETCH.search(latest_query): return Intent('fetch_paper', 0.9, slots)

    # 🚀 If history exists (e.g. "what about part b?"), escalate to the LLM
    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are the intent router for the PaperSloth university exam assistant. "
         "Analyze the user's latest query in the context of the conversation history. "
         "Extract the intent and inherited slots. "
         "CRITICAL: If they ask a follow-up (e.g. 'what about part b?'), you MUST inherit "
         "the course_code, year, and question_number from the previous messages."
        ),
        # This injects the SQLite history directly into the prompt!
        MessagesPlaceholder(variable_name="messages") 
    ])
    
    chain = prompt | _get_llm_classifier()
    
    try:
        result: IntentResult = chain.invoke({"messages": messages})
        # Merge anything regex found with what the LLM inferred
        final_slots = {**result.slots.model_dump(exclude_none=True), **slots}
        return Intent(type=result.type, confidence=result.confidence, slots=final_slots)
    except Exception:
        return Intent("rag_search", 0.5, {})