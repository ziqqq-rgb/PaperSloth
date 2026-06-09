"""
services/agent/helpers.py
─────────────────────────
Pure utility functions shared across agent handlers.
No imports from the agent package itself (no circular deps).
"""

import re
from typing import Any, Optional

from core.database import execute_query


def extract_sub_parts(full_text: str, children: Any) -> list[str]:
    """
    Infer sub-part labels (a, b, c …) from question text or children list.
    Only matches (a)/(b)/(c) style — not (1)/(2)/(3).
    """
    if children and isinstance(children, list) and len(children) > 1:
        return [str(chr(97 + i)) for i in range(len(children))]

    parts = re.findall(r'\(([a-z])\)', full_text[:800])
    seen: set = set()
    unique: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique or []


def extract_course(query: str) -> Optional[str]:
    """
    Try to infer a course code from free text.
    1. Pattern match e.g. "UPCE3273"
    2. Fuzzy search exam_papers.subject_name
    """
    m = re.search(r"\b([A-Z]{2,4}\d{4})\b", query, re.I)
    if m:
        return m.group(1).upper()

    keywords = [
        w for w in re.findall(r"\b[a-zA-Z]{4,}\b", query)
        if w.lower() not in {
            "give", "show", "what", "from", "help", "with",
            "that", "came", "topics", "question", "paper", "find",
        }
    ][:3]

    if not keywords:
        return None

    conditions = " AND ".join("subject_name ILIKE %s" for _ in keywords)
    row = execute_query(
        f"SELECT course_code FROM exam_papers WHERE {conditions} LIMIT 1",
        [f"%{k}%" for k in keywords],
        fetch="one",
    )
    return row[0] if row else None