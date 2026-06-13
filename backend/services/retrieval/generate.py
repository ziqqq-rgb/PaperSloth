import json
import re
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

# Lines that signal the model is "thinking out loud" rather than answering.
# Catches first-person reasoning narration regardless of bullet style
# ('*', '-', numbered, or plain prose), e.g.:
#   "Wait, if I look at the prompt..."
#   "In the context of RBB3013..."
#   "However, since it's the only thing that matches..."
#   "Actually, looking at Q4b..."
#   "I will provide the entire Q4."
#   "One more check: Is there any other question?"
_THINKING_LINE = re.compile(
    r"^\s*"
    r"(?:[*\-•]\s*|\d+[.)]\s*)?"          # optional bullet/number prefix
    r"(?:"
    r"wait,?\b"
    r"|hmm,?\b"
    r"|let me\b"
    r"|i (?:will|should|need to|think|have to|'ll)\b"
    r"|i'm going to\b"
    r"|in the context of\b"
    r"|however,?\s+(?:since|because|given)\b"
    r"|actually,?\s+(?:looking|checking|wait)\b"
    r"|one more check\b"
    r"|let'?s (?:check|see|verify|confirm)\b"
    r"|first,?\s+(?:i|let|check)\b"
    r"|to (?:decide|determine|figure out)\b.*\?\s*$"
    r")",
    re.IGNORECASE,
)

# A line that looks like the start of a real exam-question answer:
# course code / "Q<number>" / "[<...marks>]" / question-number labels.
_ANSWER_START = re.compile(
    r"^\s*"
    r"(?:[*\-•]\s*|\d+[.)]\s*)?"
    r"(?:[A-Z]{2,4}\d{3,4}\b"             # course code, e.g. RBB3013
    r"|Q\d+[a-z]?\b"                       # Q4, Q4b
    r"|\[.*\b(?:marks?|RBB|EDB)\b)",       # "[RBB3013 | ... | Q4 | 20 marks]"
)


def strip_thinking(text: str) -> str:
    """
    Remove chain-of-thought / reasoning preamble from Gemma/Gemini output.

    Two passes:
      1. (Legacy) If the whole response starts with '*' bullets, skip every
         leading blank/'*' line until the first non-bullet content line.
      2. (New) Walk the response line by line. Drop any leading run of lines
         that match _THINKING_LINE (first-person reasoning narration in any
         bullet style). Stop dropping as soon as either a line matches
         _ANSWER_START, or a line matches neither pattern but looks like
         real content (non-empty, doesn't look like meta-commentary).

    If everything looks like thinking, return the original text unchanged
    rather than returning an empty string — better to show something than
    nothing.
    """
    text = text.strip()
    if not text:
        return text

    lines = text.splitlines()

    # ── Pass 1: legacy '*'-bullet stripping (kept for backwards compatibility)
    if text.startswith("*"):
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("*"):
                lines = lines[i:]
                text  = "\n".join(lines).strip()
                break
        else:
            # entire response was '*' bullets — fall through to pass 2,
            # which may still find an answer-shaped line inside them.
            pass

    # ── Pass 2: drop leading reasoning-narration lines ───────────────────────
    cut = 0
    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            cut = i + 1
            continue

        if _ANSWER_START.match(stripped):
            # Found the real answer — stop here.
            break

        if _THINKING_LINE.match(stripped):
            cut = i + 1
            continue

        # Line doesn't match either pattern. If we haven't found an
        # answer-shaped line yet, be conservative: treat short/meta-looking
        # lines (ending in '?', or very short) as still-thinking, otherwise
        # treat this as the start of real content.
        if stripped.endswith("?") and len(stripped) < 120:
            cut = i + 1
            continue

        break

    if cut == 0:
        return text  # nothing matched as thinking — return as-is

    remainder = "\n".join(lines[cut:]).strip()
    return remainder or text  # never return empty


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