import json
from typing import Generator

import google.generativeai as genai

from core.config import settings
from services.prompts import TUTOR_SYSTEM, RAG_SYSTEM

# Generation config shared by every Gemini call.
# thinking_budget=0 disables chain-of-thought on Gemini 2.x / Gemma models.
_GEN_CONFIG = {"temperature": 0.1}

# Re-stream chunk size (characters)
_CHUNK = 40


# ── Model factory ─────────────────────────────────────────────────────────────

def build_rag_model() -> genai.GenerativeModel:
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=RAG_SYSTEM,
    )


def build_tutor_model() -> genai.GenerativeModel:
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(
        settings.gemini_flash_model,
        system_instruction=TUTOR_SYSTEM,
    )


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(query: str, parents: list[dict]) -> str:
    parts = []
    for doc in parents:
        header = (
            f"[{doc['course_code']} | {doc['semester']} {doc['year']} | "
            f"Q{doc['question_number']} | {doc['total_marks']} marks]"
        )
        parts.append(f"{header}\n{doc['full_text']}")
    context = "\n\n---\n\n".join(parts)
    return f"EXAM QUESTIONS:\n{context}\n\nSTUDENT: {query}"


# ── Thinking strip ────────────────────────────────────────────────────────────

def strip_thinking(text: str) -> str:
    """
    Remove chain-of-thought preamble from Gemma/Gemini output.

    The model outputs thinking as bullet lines starting with '*'.
    We skip every leading line that is blank or starts with '*',
    then return everything from the first real content line onward.
    """
    text = text.strip()
    if not text.startswith("*"):
        return text

    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("*"):
            return "\n".join(lines[i:]).strip()

    return text  # entire response was bullets — return as-is


# ── Streaming helper ──────────────────────────────────────────────────────────

def stream_text(model: genai.GenerativeModel, prompt: str) -> Generator[str, None, None]:
    """
    Buffer the full response (to strip thinking), then re-stream in small
    chunks so the frontend still animates.

    Yields SSE token events and a final done event.
    """
    full_text = ""
    for chunk in model.generate_content(prompt, stream=True, generation_config=_GEN_CONFIG):
        if chunk.text:
            full_text += chunk.text

    clean = strip_thinking(full_text)

    for i in range(0, len(clean), _CHUNK):
        yield f"data: {json.dumps({'type': 'token', 'token': clean[i:i+_CHUNK]})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"