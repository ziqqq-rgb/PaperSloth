"""
image_handler.py
----------------
Extracts images from a Docling-parsed exam paper, saves them to disk
(or uploads to Supabase Storage), and links each image back to its
parent QuestionChunk by page proximity.

Usage:
    from image_handler import extract_and_link_images

    result  = converter.convert("paper.pdf")
    doc     = result.document
    chunks  = chunk_questions(doc)          # from question_chunker.py

    # Save locally
    chunks  = extract_and_link_images(doc, chunks, output_dir="./images")

    # Or upload to Supabase (set env vars SUPABASE_URL + SUPABASE_KEY)
    chunks  = extract_and_link_images(doc, chunks, use_supabase=True,
                                      supabase_bucket="exam-images")
"""

from __future__ import annotations

import io
import os
import hashlib
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from question_chunker import QuestionChunk


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


def _image_hash(image_bytes: bytes) -> str:
    return hashlib.md5(image_bytes).hexdigest()[:12]


def _get_image_bytes(pic) -> Optional[bytes]:
    """
    Try every known Docling API to get raw image bytes from a picture element.
    Docling's API changed across minor versions, so we probe all known paths.
    """
    # Method 1: pic.image.pil_image  (most common in recent versions)
    try:
        pil_img = pic.image.pil_image
        if pil_img is not None:
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        pass

    # Method 2: pic.get_image()
    try:
        pil_img = pic.get_image()
        if pil_img is not None:
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        pass

    # Method 3: pic.image.uri  (file URI to a temp file Docling wrote)
    try:
        uri = str(pic.image.uri)
        if uri.startswith("file://"):
            path = uri[7:]
        else:
            path = uri
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception:
        pass

    return None  # could not extract


def _save_locally(image_bytes: bytes, output_dir: Path, filename: str) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return str(filepath)


def _upload_supabase(image_bytes: bytes, bucket: str, filename: str) -> Optional[str]:
    """
    Upload image to Supabase Storage.
    Requires env vars: SUPABASE_URL, SUPABASE_KEY
    Requires: pip install supabase
    """
    try:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        client = create_client(url, key)
        res = client.storage.from_(bucket).upload(
            path=filename,
            file=image_bytes,
            file_options={"content-type": "image/png"},
        )
        # Build public URL
        public_url = client.storage.from_(bucket).get_public_url(filename)
        return public_url
    except Exception as e:
        print(f"[image_handler] Supabase upload failed for {filename}: {e}")
        return None


# ---------------------------------------------------------------------------
# Page → chunk mapping helper
# ---------------------------------------------------------------------------

def _build_page_to_chunk_map(chunks: list["QuestionChunk"]) -> dict[int, "QuestionChunk"]:
    """
    Map each page number to the chunk whose question starts on (or nearest to) that page.
    Images on a page are attributed to that page's chunk.
    If multiple chunks share a page, the first one wins (conservative).
    """
    page_map: dict[int, "QuestionChunk"] = {}
    for chunk in chunks:
        for page in chunk.page_numbers:
            if page not in page_map:
                page_map[page] = chunk
    return page_map


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_and_link_images(
    doc,
    chunks: list["QuestionChunk"],
    output_dir: str = "./extracted_images",
    paper_id: str = "paper",
    use_supabase: bool = False,
    supabase_bucket: str = "exam-images",
) -> list["QuestionChunk"]:
    """
    Extract all images from a Docling document, save or upload them,
    and attach the resulting URLs/paths to the appropriate QuestionChunk.

    Args:
        doc:             Docling DoclingDocument object.
        chunks:          List of QuestionChunks from chunk_questions().
        output_dir:      Local directory to save images (used if use_supabase=False).
        paper_id:        Identifier prefix for image filenames (e.g. exam paper UUID).
        use_supabase:    If True, upload to Supabase; requires SUPABASE_URL + SUPABASE_KEY.
        supabase_bucket: Supabase Storage bucket name.

    Returns:
        The same chunks list, with has_image and image_refs updated in-place.
    """
    if not doc.pictures:
        print("[image_handler] No pictures found in document.")
        return chunks

    page_to_chunk = _build_page_to_chunk_map(chunks)
    out_path = Path(output_dir)
    saved_count = 0
    failed_count = 0

    for idx, pic in enumerate(doc.pictures):
        page = _get_page(pic)
        image_bytes = _get_image_bytes(pic)

        if image_bytes is None:
            print(f"[image_handler] WARNING: Could not extract image #{idx} on page {page}. "
                  f"This may mean Docling didn't materialise images — "
                  f"set pipeline_options.images_scale=2.0 to enable image extraction.")
            failed_count += 1
            continue

        h = _image_hash(image_bytes)
        filename = f"{paper_id}_p{page}_img{idx}_{h}.png"

        if use_supabase:
            url = _upload_supabase(image_bytes, supabase_bucket, filename)
        else:
            url = _save_locally(image_bytes, out_path, filename)

        if url is None:
            failed_count += 1
            continue

        # Link image to the chunk that owns this page
        target_chunk = page_to_chunk.get(page)
        if target_chunk:
            target_chunk.has_image = True
            target_chunk.image_refs.append(url)
        else:
            # Page not in any chunk (e.g. cover page) — attach to first chunk
            if chunks:
                chunks[0].image_refs.append(url)
                print(f"[image_handler] Image on page {page} has no matching chunk; "
                      f"attached to first chunk.")

        saved_count += 1

    print(f"[image_handler] Done. Saved: {saved_count}, Failed: {failed_count}, "
          f"Total pictures: {len(doc.pictures)}")
    return chunks


# ---------------------------------------------------------------------------
# Enable image materialisation in Docling (call this BEFORE converting)
# ---------------------------------------------------------------------------

def get_pipeline_options_with_images(num_threads: int = 4):
    """
    Returns PdfPipelineOptions configured to materialise images.
    Use this when setting up the DocumentConverter.

    Example:
        from image_handler import get_pipeline_options_with_images
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat

        pipeline_options = get_pipeline_options_with_images()
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    """
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        AcceleratorOptions,
        AcceleratorDevice,
    )

    opts = PdfPipelineOptions()
    opts.images_scale = 2.0           # materialise images at 2x scale (PNG)
    opts.generate_picture_images = True
    opts.accelerator_options = AcceleratorOptions(
        num_threads=num_threads,
        device=AcceleratorDevice.CPU,
    )
    return opts