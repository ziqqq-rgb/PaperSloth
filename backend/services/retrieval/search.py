import base64
import mimetypes
from typing import Optional

import requests
from sentence_transformers import CrossEncoder

from core.config import settings
from core.database import execute_query


# ── Metadata filter builder ───────────────────────────────────────────────────

def build_filter(
    course_code:   Optional[str] = None,
    year:          Optional[int] = None,
    semester:      Optional[str] = None,
    question_type: Optional[str] = None,
    min_marks:     Optional[int] = None,
) -> dict:
    f = {}
    if course_code:   f["course_code"]  = {"$eq": course_code}
    if year:          f["year"]          = {"$eq": year}
    if semester:      f["semester"]      = {"$eq": semester}
    if question_type: f["question_type"] = {"$eq": question_type}
    if min_marks:     f["marks"]         = {"$gte": min_marks}
    return f


# ── Reranker ──────────────────────────────────────────────────────────────────

def build_reranker() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)


def rerank(reranker: CrossEncoder, query: str, matches: list, top_n: int = 5) -> list:
    if not matches:
        return []
    passages = [m.metadata.get("text_preview", "") for m in matches]
    scores   = reranker.predict([(query, p) for p in passages])
    ranked   = sorted(zip(matches, scores), key=lambda x: x[1], reverse=True)
    return [m for m, _ in ranked[:top_n]]


# ── Image fetch ───────────────────────────────────────────────────────────────

def _url_to_base64(url: str) -> str:
    """Fetch image from Supabase storage and return as base64 data URI."""
    clean_url = url.replace("/rest/v1/storage/", "/storage/")
    headers = {
        "apikey":        settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
    }
    try:
        resp = requests.get(clean_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            mime = resp.headers.get("content-type", "image/png").split(";")[0]
            b64  = base64.b64encode(resp.content).decode()
            return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return url  # fallback to original URL


# ── Parent fetch ──────────────────────────────────────────────────────────────

def fetch_parents(parent_ids: list[str]) -> list[dict]:
    if not parent_ids:
        return []
    rows = execute_query(
        """
        SELECT parent_id, question_number, full_text, total_marks,
               image_urls, course_code, semester, year
        FROM   parent_chunks
        WHERE  parent_id = ANY(%s)
        """,
        (parent_ids,),
    )
    results = []
    for r in (rows or []):
        raw_urls = r[4] or {}
        b64_urls = {label: _url_to_base64(url) for label, url in raw_urls.items()}
        results.append({
            "parent_id":       r[0],
            "question_number": r[1],
            "full_text":       r[2],
            "total_marks":     r[3],
            "image_urls":      b64_urls,
            "course_code":     r[5],
            "semester":        r[6],
            "year":            r[7],
        })
    return results