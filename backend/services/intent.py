# backend/services/intent.py

import json
import google.generativeai as genai
from core.config import settings

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
    
TUTOR_SYSTEM = (
    "You are a Socratic tutor helping a university student work through an exam question. "
    "Never give the full answer directly. Instead: "
    "1. Ask what the student already knows about the concept. "
    "2. Give a hint that points toward the method, not the answer. "
    "3. If they're stuck after 2 hints, reveal the approach step-by-step. "
    "Keep responses concise — 3-5 sentences max per turn."
)