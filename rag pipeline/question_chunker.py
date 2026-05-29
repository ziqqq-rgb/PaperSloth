"""
question_chunker.py
-------------------
Splits a Docling-parsed UTP exam paper into one QuestionChunk per main question.

UTP papers are often scanned. OCR frequently drops question numbers ("1.", "3.", "4."),
so we use MULTIPLE detection strategies in priority order:

  1. "2 a. FIGURE..." format  → catches "2 a." style labels (common in scanned papers)
  2. "1. You..." format       → number + dot + space (digital papers)
  3. "FIGURE Q3 shows..."     → infer question number from figure label
  4. First page of content    → treat as Q1 if no boundary was found before it

Usage:
    from question_chunker import chunk_questions
    chunks = chunk_questions(doc)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class QuestionChunk:
    """One main exam question extracted from a paper."""

    question_number: str
    question_text: str
    page_numbers: list[int]         = field(default_factory=list)
    marks: Optional[int]            = None
    has_image: bool                 = False
    question_type: str              = "text"   # "text" | "calculation" | "diagram"
    image_refs: list[str]           = field(default_factory=list)

    def __repr__(self) -> str:
        preview = self.question_text[:80].replace("\n", " ")
        return (
            f"QuestionChunk(q='{self.question_number}', level='main', "
            f"marks={self.marks}, pages={self.page_numbers}, "
            f"has_image={self.has_image}, "
            f"text='{preview}...')"
        )

    def to_dict(self) -> dict:
        return {
            "question_number": self.question_number,
            "question_text":   self.question_text,
            "page_numbers":    self.page_numbers,
            "marks":           self.marks,
            "has_image":       self.has_image,
            "question_type":   self.question_type,
            "image_refs":      self.image_refs,
        }


# ---------------------------------------------------------------------------
# Configuration — adjust these if papers use different formats
# ---------------------------------------------------------------------------

# Pages to keep (skip cover page and appendix)
CONTENT_START_PAGE = 2    # first page with questions
CONTENT_END_PAGE   = 8    # pages >= this are skipped (appendix, formula sheets)

# Text fragments that are pure noise — discard completely
_NOISE_EXACT = {
    "SULIT", "CONFIDENTIAL", "END OF PAPER", "- END OF PAPER -",
    "Universiti Teknologi PETRONAS", "FINAL EXAMINATION",
}

_NOISE_PATTERNS = [
    re.compile(r"^\d{1,2}$"),            # standalone page numbers  "2", "3" ...
    re.compile(r"^[_\-\.·~\s]+$"),       # divider lines  "---", "..."
    re.compile(r"^['\",\.:;!?]{1,4}$"),  # stray OCR punctuation
    re.compile(r"^[A-Za-z0-9]{1,2}$"),   # very short OCR noise  "L", "W", "SY"
    re.compile(r"^\d{1,2}\s*$"),         # number + whitespace only
    re.compile(r"^[·•]\s*$"),            # bullet with nothing
    re.compile(r"^[+\-]\s*$"),           # stray "+" or "-" from circuit diagrams
]

# Marks pattern:  "[10 marks]"  "[5 marks]."
_MARKS_RE = re.compile(r"\[(\d+)\s*marks?\]", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Question boundary detection — returns (question_number | None)
# ---------------------------------------------------------------------------

def _detect_boundary(text: str) -> Optional[str]:
    """
    Return the question number string if `text` marks the start of a new
    main question, otherwise return None.

    Detection strategies (in priority order):
      1. "2 a. FIGURE..."  — number + space + letter + dot  (scanned UTP format)
      2. "1. a."           — number + dot + space (digital format)
      3. "FIGURE Q3 shows" — infer from figure label
    """
    t = text.strip()

    # Strategy 1 — "2 a. FIGURE..." or "3 b. A multirange..."
    # Matches:  "2 a. ", "3 b. ", "4 c. " etc.
    m = re.match(r"^(\d{1,2})\s+[a-z]\.\s+\S", t)
    if m:
        return m.group(1)

    # Strategy 2 — "1. a." or "1. You would like..."
    # Matches:  "1. ", "2. ", "10. " etc.
    m = re.match(r"^(\d{1,2})\.\s+[A-Za-z]", t)
    if m:
        return m.group(1)

    # Strategy 3 — "FIGURE Q3 shows..." or "FIGURE Q4"
    # When OCR drops the question number, the figure label still carries it
    m = re.match(r"^FIGURE\s+Q(\d+)", t, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_noise(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if t in _NOISE_EXACT:
        return True
    # Also skip anything that IS a course code header (e.g. "RBB3013")
    if re.match(r"^[A-Z]{2,4}\d{4}$", t):
        return True
    for pat in _NOISE_PATTERNS:
        if pat.match(t):
            return True
    return False


def _extract_marks(text: str) -> Optional[int]:
    """Return the highest mark value found in the text, or None."""
    hits = _MARKS_RE.findall(text)
    return max(int(h) for h in hits) if hits else None


def _classify_type(text: str, has_image: bool) -> str:
    if has_image:
        return "diagram"
    calc_keywords = [
        "calculate", "determine", "evaluate", "solve", "compute",
        "find the", "derive", "prove", "show that", "analyse whether",
    ]
    if any(kw in text.lower() for kw in calc_keywords):
        return "calculation"
    return "text"


def _flush(
    q_num: str,
    pages: list[int],
    lines: list[str],
    out: list[QuestionChunk],
) -> None:
    if not lines:
        return
    full_text = "\n".join(lines)
    marks     = _extract_marks(full_text)
    has_img   = False  # set later by image_handler.extract_and_link_images()
    out.append(QuestionChunk(
        question_number = q_num,
        question_text   = full_text,
        page_numbers    = sorted(set(pages)),
        marks           = marks,
        has_image       = has_img,
        question_type   = _classify_type(full_text, has_img),
    ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_questions(
    doc,
    content_start_page: int = CONTENT_START_PAGE,
    content_end_page:   int = CONTENT_END_PAGE,
) -> list[QuestionChunk]:
    """
    Segment a Docling DoclingDocument into one QuestionChunk per main question.

    Args:
        doc:                Parsed DoclingDocument from Docling.
        content_start_page: First page with question content (skip cover).
        content_end_page:   Pages >= this are skipped (appendix / formula sheet).

    Returns:
        List of QuestionChunk — one per detected main question.
    """

    print(f"[chunker] Processing pages {content_start_page}–{content_end_page - 1} "
          f"(skipping cover p1, appendix p{content_end_page}+)")

    # ── Step 1: collect content items in page order ──────────────────────────
    items: list[tuple[int, str]] = []   # (page_no, text)
    for item in doc.texts:
        page = 0
        if hasattr(item, "prov") and item.prov:
            page = item.prov[0].page_no

        if page < content_start_page or page >= content_end_page:
            continue

        text = item.text.strip()
        if _is_noise(text):
            continue

        items.append((page, text))

    if not items:
        print("[chunker] WARNING: No content items after filtering. "
              "Check content_start_page / content_end_page settings.")
        return []

    # ── Step 2: walk items, flush on boundary detections ─────────────────────
    chunks: list[QuestionChunk] = []
    current_q:     Optional[str]  = None
    current_pages: list[int]      = []
    current_lines: list[str]      = []

    for page, text in items:
        q_num = _detect_boundary(text)

        if q_num is not None:
            # Save previous question before starting new one
            if current_q is not None:
                _flush(current_q, current_pages, current_lines, chunks)

            current_q     = q_num
            current_pages = [page]
            current_lines = [text]

        else:
            if current_q is not None:
                current_pages.append(page)
                current_lines.append(text)
            # Content before first detected boundary → skip
            # (these are usually instructions / notes on the cover/intro)

    # Flush the last question
    if current_q is not None:
        _flush(current_q, current_pages, current_lines, chunks)

    # ── Step 3: fallback if nothing was detected ──────────────────────────────
    if not chunks:
        print(
            "[chunker] WARNING: No question boundaries detected.\n"
            "  Possible causes:\n"
            "    1. Scanned PDF with poor OCR — question numbers not extracted\n"
            "    2. Paper uses unusual numbering format\n"
            "  Returning full content as a single chunk for inspection."
        )
        all_text = "\n".join(t for _, t in items)
        pages    = sorted(set(p for p, _ in items))
        return [QuestionChunk(
            question_number = "?",
            question_text   = all_text,
            page_numbers    = pages,
            marks           = _extract_marks(all_text),
            has_image       = False,
            question_type   = "text",
        )]

    print(f"[chunker] Detected {len(chunks)} question(s): "
          + ", ".join(f"Q{c.question_number}" for c in chunks))

    return chunks