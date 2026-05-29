"""
question_chunker.py
-------------------
Splits a Docling-parsed exam paper into question-level chunks.

Handles UTP exam paper patterns (validated against RBB3013 Sept 2025):
  3-level hierarchy:
    Level 1 — "1."  "2."  "3."  "4."          (main questions)
    Level 2 — "a."  "b."  "c."                 (letter sub-questions)
    Level 3 — "i."  "ii." "iii."               (roman numeral sub-sub-questions)

Key design decisions:
  - Cover page (page 1) is always skipped
  - Appendix pages are auto-detected and skipped
  - Instructions section (numbered 1–5 on cover) cannot trigger false positives
    because page 1 is skipped entirely
  - Roman numerals only trigger if a letter-level parent exists
  - split_level controls how deep to split:
      "main"   → only Q1, Q2, Q3, Q4
      "letter" → Q1a, Q1b, Q2a, Q2b ...  (recommended)
      "roman"  → Q1ai, Q1aii, Q2ai ...   (most granular)

Usage:
    from question_chunker import chunk_questions

    result = converter.convert("paper.pdf")
    doc    = result.document
    chunks = chunk_questions(doc, split_level="letter")
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
    question_number: str          # e.g. "1a", "1bi", "3c"
    question_text:   str
    marks:           Optional[int]
    page_numbers:    list[int]
    level:           str          # "main" | "letter" | "roman"
    parent:          Optional[str]
    has_image:       bool = False
    image_refs:      list[str] = field(default_factory=list)
    question_type:   Optional[str] = None
    raw_elements:    list[dict] = field(default_factory=list)

    def __repr__(self) -> str:
        preview = self.question_text[:80].replace("\n", " ")
        return (
            f"QuestionChunk(q={self.question_number!r}, level={self.level!r}, "
            f"marks={self.marks}, pages={self.page_numbers}, "
            f"has_image={self.has_image}, text={preview!r}...)"
        )

    def to_dict(self) -> dict:
        return {
            "question_number": self.question_number,
            "level":           self.level,
            "parent":          self.parent,
            "question_text":   self.question_text,
            "marks":           self.marks,
            "page_numbers":    self.page_numbers,
            "has_image":       self.has_image,
            "image_refs":      self.image_refs,
            "question_type":   self.question_type,
        }


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Level 1: "1." / "2." / "3." etc.
# Standalone MUST have period or paren — bare "2" or "3" (page numbers) will NOT match.
# Inline form requires non-whitespace after separator.
_MAIN_Q = re.compile(
    r"^([1-9])\s*[\.\)]\s*$"       # standalone: "1." or "2." (period required)
    r"|^([1-9])\s*[\.\)]\s+\S",    # inline:     "1. text..."
    re.IGNORECASE,
)

# Level 2: "a." / "(a)" — standalone or inline
# Standalone MUST have period or paren — bare "W", "R", "M" (diagram labels) will NOT match.
_LETTER_Q = re.compile(
    r"^\(?([a-z])\)?\s*[\.\)]\s*$"     # standalone: "a." (period required)
    r"|^\(?([a-z])\)?[\.\)]\s+\S",     # inline:     "a. text..."
    re.IGNORECASE,
)

# Level 3: "i." / "(i)" — standalone or inline
_ROMAN_Q = re.compile(
    r"^\(?([ivx]+)\)?\s*[\.\)]\s*$"    # standalone: "i." (period required)
    r"|^\(?([ivx]+)\)?[\.\)]\s+\S",    # inline:     "i. text..."
    re.IGNORECASE,
)

# Marks: "[5 marks]", "(5 marks)", "5 marks" at end of a line
_MARKS = re.compile(
    r"[\[\(]?\s*(\d{1,3})\s*marks?\s*[\]\)]?\s*$",
    re.IGNORECASE,
)

# Appendix / end-of-paper markers — must be a SHORT standalone line (heading),
# not mid-sentence like "...given in APPENDIX I, solve the voltage..."
_APPENDIX = re.compile(
    r"^(?:appendix\s*[ivx\d]*|end\s+of\s+(?:paper|exam(?:ination)?))\s*$",
    re.IGNORECASE,
)

# Lines that look like cover page / admin content (secondary guard in case
# page filtering misses something)
_ADMIN_LINE = re.compile(
    r"""
    ^(?:
        universiti\s+teknologi           # "Universiti Teknologi PETRONAS"
        | final\s+exam(?:ination)?       # "Final Examination"
        | instructions?\s+to\s+cand     # "Instructions to Candidates"
        | answer\s+all\s+questions       # instruction line
        | begin\s+each\s+answer          # instruction line
        | do\s+not\s+open                # instruction line
        | indicate\s+clearly             # instruction line
        | where\s+applicable             # instruction line
        | graph\s+papers?\s+will         # note line
        | double.sided                   # note line
        | there\s+are\s+ten              # note line
        | page\s*\d+                     # page number
        | \d+\s*/\s*\d+                  # "2 / 10"
        | rbb\d+                         # course code header like "RBB3013"
        | [a-z]{2,6}\d{4}               # any course code header
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_page(element) -> int:
    try:
        if hasattr(element, "prov") and element.prov:
            return element.prov[0].page_no
    except Exception:
        pass
    return 0


def _extract_marks(text: str) -> Optional[int]:
    for line in reversed(text.splitlines()):
        m = _MARKS.search(line.strip())
        if m:
            val = int(m.group(1))
            if 1 <= val <= 100:
                return val
    return None


def _classify_type(text: str, has_image: bool) -> str:
    t = text.lower()
    if has_image or re.search(r"\bdraw\b|\bsketch\b|\bdiagram\b|\bfigure\b", t):
        return "diagram"
    if re.search(r"\bcalculat|comput|evaluat|solv|find the value|determine\b", t):
        return "calculation"
    return "theory"


def _is_roman(s: str) -> bool:
    """True if s is a valid roman numeral (i–x range)."""
    return bool(re.fullmatch(r"[ivx]+", s.lower()))


def _roman_to_int(s: str) -> int:
    vals = {"i": 1, "v": 5, "x": 10}
    s = s.lower()
    total = 0
    for i, c in enumerate(s):
        if i + 1 < len(s) and vals.get(c, 0) < vals.get(s[i + 1], 0):
            total -= vals.get(c, 0)
        else:
            total += vals.get(c, 0)
    return total


# ---------------------------------------------------------------------------
# Page-range filtering
# ---------------------------------------------------------------------------

def _find_question_page_range(doc) -> tuple[int, int]:
    """
    Returns (first_question_page, last_question_page).
    - Always skip page 1 (cover page in UTP papers)
    - Detect appendix start and stop before it
    """
    first_page = 2          # UTP cover is always page 1
    last_page  = len(doc.pages)

    for item in doc.texts:
        text = item.text.strip() if hasattr(item, "text") else ""
        if _APPENDIX.search(text):
            pg = _get_page(item)
            if pg > first_page:
                last_page = pg - 1
                break

    return first_page, last_page


# ---------------------------------------------------------------------------
# Core chunker
# ---------------------------------------------------------------------------

def chunk_questions(
    doc,
    split_level: str = "letter",    # "main" | "letter" | "roman"
) -> list[QuestionChunk]:
    """
    Parse a Docling DoclingDocument and return QuestionChunks.

    split_level controls depth:
      "main"   → one chunk per main question (1, 2, 3, 4)
      "letter" → one chunk per lettered sub-question (1a, 1b, 2a ...)  ← recommended
      "roman"  → one chunk per roman sub-question (1ai, 1aii, 2ai ...)
    """

    # ------------------------------------------------------------------ #
    # 1. Find question pages (skip cover + appendix)                      #
    # ------------------------------------------------------------------ #
    first_pg, last_pg = _find_question_page_range(doc)
    print(f"[chunker] Processing pages {first_pg}–{last_pg} "
          f"(skipping cover p1, appendix p{last_pg + 1}+)")

    # ------------------------------------------------------------------ #
    # 2. Collect text elements within question page range                 #
    # ------------------------------------------------------------------ #
    elements: list[dict] = []
    for item in doc.texts:
        pg = _get_page(item)
        if pg < first_pg or pg > last_pg:
            continue
        text = item.text.strip() if hasattr(item, "text") else ""
        if not text:
            continue
        # Skip admin lines that slipped through
        first_line = text.splitlines()[0].strip()
        if _ADMIN_LINE.match(first_line):
            continue
        elements.append({
            "text":  text,
            "page":  pg,
            "label": str(getattr(item, "label", "text")).lower(),
        })

    # Pages with pictures (within question range)
    picture_pages: set[int] = set()
    for pic in doc.pictures:
        pg = _get_page(pic)
        if first_pg <= pg <= last_pg:
            picture_pages.add(pg)

    # ------------------------------------------------------------------ #
    # 3. Detect boundaries with level tracking                            #
    # ------------------------------------------------------------------ #
    # boundary = {q_num, start_idx, level, parent}
    boundaries: list[dict] = []

    last_main:   Optional[str] = None
    last_letter: Optional[str] = None

    for idx, el in enumerate(elements):
        first_line = el["text"].splitlines()[0].strip()

        # Skip OCR noise — single chars or very short fragments from diagrams
        if len(el["text"].strip()) < 4:
            continue

        # --- Level 1: main question ---
        m = _MAIN_Q.match(first_line)
        if m:
            q = (m.group(1) or m.group(2))   # group 1 = standalone, 2 = inline
            boundaries.append({"q_num": q, "start_idx": idx,
                                "level": "main", "parent": None})
            last_main   = q
            last_letter = None
            continue

        # --- Level 2: letter sub-question (only if split_level allows) ---
        if split_level in ("letter", "roman") and last_main:
            m = _LETTER_Q.match(first_line)
            if m:
                letter = (m.group(1) or m.group(2)).lower()
                q = f"{last_main}{letter}"
                boundaries.append({"q_num": q, "start_idx": idx,
                                    "level": "letter", "parent": last_main})
                last_letter = q
                continue

        # --- Level 3: roman sub-sub-question (only if split_level allows) ---
        if split_level == "roman" and last_letter:
            m = _ROMAN_Q.match(first_line)
            if m and _is_roman(m.group(1) or m.group(2)):
                roman = (m.group(1) or m.group(2)).lower()
                q = f"{last_letter}{roman}"
                boundaries.append({"q_num": q, "start_idx": idx,
                                    "level": "roman", "parent": last_letter})
                continue

    if not boundaries:
        print("[chunker] WARNING: No question boundaries detected. "
              "Check PDF extraction quality or adjust regex patterns.")
        full_text = "\n".join(el["text"] for el in elements)
        pages = sorted({el["page"] for el in elements})
        has_img = bool(picture_pages)
        return [QuestionChunk(
            question_number="1", question_text=full_text,
            marks=_extract_marks(full_text), page_numbers=pages,
            level="main", parent=None, has_image=has_img,
            question_type=_classify_type(full_text, has_img),
            raw_elements=elements,
        )]

    # ------------------------------------------------------------------ #
    # 4. Slice elements into chunks                                       #
    # ------------------------------------------------------------------ #
    chunks: list[QuestionChunk] = []

    for i, boundary in enumerate(boundaries):
        start = boundary["start_idx"]
        end   = boundaries[i + 1]["start_idx"] if i + 1 < len(boundaries) else len(elements)

        chunk_els  = elements[start:end]
        full_text  = "\n".join(el["text"] for el in chunk_els).strip()
        pages      = sorted({el["page"] for el in chunk_els})
        has_img    = bool(picture_pages & set(pages))
        marks      = _extract_marks(full_text)

        chunks.append(QuestionChunk(
            question_number = boundary["q_num"],
            question_text   = full_text,
            marks           = marks,
            page_numbers    = pages,
            level           = boundary["level"],
            parent          = boundary["parent"],
            has_image       = has_img,
            question_type   = _classify_type(full_text, has_img),
            raw_elements    = chunk_els,
        ))

    return chunks