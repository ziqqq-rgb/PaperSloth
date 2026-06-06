"""
services/storage.py
───────────────────
Supabase Storage helpers for exam PDF management.

Bucket layout:
  exam-papers/
    EDB2613/2024/MAY 2024 SEMESTER.pdf
    EDB2613/2023/JANUARY 2023 SEMESTER.pdf
    RBB3013/2025/May 2025.pdf
    ...

Signed URLs expire after 1 hour — the frontend opens them in a new tab
immediately, so expiry is never an issue in normal use.
"""

import requests
from core.config import settings

BUCKET = "exam-papers"


def _headers() -> dict:
    return {
        "apikey":        settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
    }


def pdf_path(course_code: str, year: int, semester: str) -> str:
    """Canonical storage path for a paper PDF."""
    return f"{course_code}/{year}/{semester}.pdf"


def create_signed_url(path: str, expires_in: int = 3600) -> str:
    """
    Request a time-limited signed download URL from Supabase Storage.
    expires_in: seconds until the URL expires (default 1 h)
    """
    url = f"{settings.supabase_url}/storage/v1/object/sign/{BUCKET}/{path}"
    resp = requests.post(
        url,
        json={"expiresIn": expires_in},
        headers=_headers(),
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Supabase sign failed [{resp.status_code}]: {resp.text}"
        )
    data = resp.json()
    signed = data.get("signedURL") or data.get("signedUrl", "")
    # Supabase sometimes returns a path-only value; prepend the base URL.
    if signed and not signed.startswith("http"):
        signed = f"{settings.supabase_url}/storage/v1{signed}"
    return signed


def upload_pdf(path: str, content: bytes, content_type: str = "application/pdf") -> str:
    """
    Upload a PDF to the exam-papers bucket.
    Returns the storage path on success, raises on failure.
    Used by admin tooling / ingestion scripts.
    """
    url = f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{path}"
    headers = {**_headers(), "Content-Type": content_type}
    resp = requests.post(url, data=content, headers=headers, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed [{resp.status_code}]: {resp.text}")
    return path