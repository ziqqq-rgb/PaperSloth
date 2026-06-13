import base64
import mimetypes
from concurrent.futures import ThreadPoolExecutor
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

# Cross-encoder score below this is treated as "not actually relevant".
# Calibrated from eval_dataset_final.json: 45 topic queries scored as low as
# -10.32, while all 10 negative queries scored between -11.38 and -10.91.
# -10.8 sits cleanly between the two distributions.
RELEVANCE_THRESHOLD = -10.8


def build_reranker() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)


def rerank(reranker: CrossEncoder, query: str, matches: list, top_n: int = 5) -> list:
    if not matches:
        return []
    passages = [m.metadata.get("text_preview", "") for m in matches]
    scores   = reranker.predict([(query, p) for p in passages])
    ranked   = sorted(zip(matches, scores), key=lambda x: x[1], reverse=True)

    # ── Relevance gate ──────────────────────────────────────────────────────
    # If even the best match scores below the threshold, the query is
    # off-topic / not covered by the corpus — return nothing rather than
    # surfacing low-confidence "relevant" results.
    if not ranked or ranked[0][1] < RELEVANCE_THRESHOLD:
        return []

    return [m for m, _ in ranked[:top_n]]


# ── Image fetch ───────────────────────────────────────────────────────────────

# Short timeout — a slow/unreachable image shouldn't block the whole response.
# Each image is fetched on its own thread (see _b64_encode_images_parallel),
# so a few slow images add latency equal to the slowest one, not the sum.
_IMAGE_FETCH_TIMEOUT = 3


def _url_to_base64(url: str) -> str:
    """Fetch image from Supabase storage and return as base64 data URI."""
    clean_url = url.replace("/rest/v1/storage/", "/storage/")
    headers = {
        "apikey":        settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
    }
    try:
        resp = requests.get(clean_url, headers=headers, timeout=_IMAGE_FETCH_TIMEOUT)
        if resp.status_code == 200:
            mime = resp.headers.get("content-type", "image/png").split(";")[0]
            b64  = base64.b64encode(resp.content).decode()
            return f"data:{mime};base64,{b64}"
    except Exception:
        pass
    return url  # fallback to original URL


def _b64_encode_images_parallel(raw_urls: dict) -> dict:
    """
    Resolve {label: url} into {label: base64_data_uri} concurrently.
    A handful of slow/unreachable images costs ~_IMAGE_FETCH_TIMEOUT seconds
    total (the slowest one), not the sum of all of them.
    """
    if not raw_urls:
        return {}
    labels = list(raw_urls.keys())
    urls   = [raw_urls[label] for label in labels]
    with ThreadPoolExecutor(max_workers=min(8, len(urls))) as pool:
        results = list(pool.map(_url_to_base64, urls))
    return dict(zip(labels, results))


# ── Parent fetch ──────────────────────────────────────────────────────────────

def fetch_parents(parent_ids: list[str], include_images: bool = True) -> list[dict]:
    """
    Fetch parent chunks by parent_id.

    include_images:
      True  → resolve image_urls to base64 data URIs (parallelized).
              Use for single-question views (e.g. fetch_paper) where the
              frontend needs the image inline immediately.
      False → return raw Supabase URLs as-is. Use for rag_search / streaming
              results, where the frontend can fetch images itself out-of-band
              without blocking the SSE response. This avoids multi-second
              sequential image downloads (and multi-MB payloads) on every
              search.
    """
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
        if include_images:
            image_urls = _b64_encode_images_parallel(raw_urls)
        else:
            image_urls = raw_urls
        results.append({
            "parent_id":       r[0],
            "question_number": r[1],
            "full_text":       r[2],
            "total_marks":     r[3],
            "image_urls":      image_urls,
            "course_code":     r[5],
            "semester":        r[6],
            "year":            r[7],
        })
    return results