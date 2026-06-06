"""
services/storage.py
───────────────────
Backblaze B2 storage for exam paper PDFs.

B2 is S3-compatible, so we use boto3 with a custom endpoint.
Free tier: 10 GB storage.

Add to .env:
    B2_ENDPOINT=https://s3.us-west-004.backblazeb2.com   # your region
    B2_KEY_ID=your_application_key_id
    B2_APP_KEY=your_application_key
    B2_BUCKET=exam-papers

Bucket layout:
  exam-papers/
    EDB2613/2024/MAY 2024 SEMESTER.pdf
    RBB3013/2025/May 2025.pdf
"""

import boto3
from botocore.config import Config
from core.config import settings

BUCKET = settings.b2_bucket


def _client():
    """Create a B2 client (S3-compatible)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.b2_endpoint,
        aws_access_key_id=settings.b2_key_id,
        aws_secret_access_key=settings.b2_app_key,
        config=Config(signature_version="s3v4"),
    )


def pdf_path(course_code: str, year: int, semester: str) -> str:
    """Canonical storage path for a paper PDF."""
    return f"{course_code}/{year}/{semester}.pdf"


def create_signed_url(path: str, expires_in: int = 3600) -> str:
    """
    Generate a pre-signed download URL (expires in 1 hour by default).
    The frontend opens this directly — no proxying through the API.
    """
    url = _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": path},
        ExpiresIn=expires_in,
    )
    return url


def upload_pdf(path: str, content: bytes, content_type: str = "application/pdf") -> str:
    """
    Upload a PDF to B2.
    Returns the storage path on success, raises on failure.
    """
    _client().put_object(
        Bucket=BUCKET,
        Key=path,
        Body=content,
        ContentType=content_type,
    )
    return path


def delete_pdf(path: str) -> None:
    """Remove a PDF from B2 (admin use)."""
    _client().delete_object(Bucket=BUCKET, Key=path)