import hashlib
import json
from typing import Optional

import redis as redis_lib

from core.config import settings

CACHE_TTL = 60 * 60 * 24  # 24 hours

try:
    _r = redis_lib.from_url(settings.redis_url, decode_responses=True)
    _r.ping()
    REDIS_ON = True
except Exception:
    _r = None
    REDIS_ON = False


def _key(query: str, filters: dict) -> str:
    raw = f"{query.strip().lower()}:{json.dumps(filters, sort_keys=True)}"
    return f"ps:{hashlib.md5(raw.encode()).hexdigest()}"


def cache_get(query: str, filters: dict) -> Optional[dict]:
    if not REDIS_ON:
        return None
    val = _r.get(_key(query, filters))
    return json.loads(val) if val else None


def cache_set(query: str, filters: dict, result: dict) -> None:
    if not REDIS_ON:
        return
    # Remove sources' full_text before caching to keep payload small
    slim = {**result, "sources": [
        {k: v for k, v in s.items() if k != "full_text"}
        for s in result.get("sources", [])
    ]}
    _r.setex(_key(query, filters), CACHE_TTL, json.dumps(slim))


def cache_status() -> dict:
    return {"available": REDIS_ON, "url": settings.redis_url if REDIS_ON else None}