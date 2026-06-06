"""
routers/papers.py
─────────────────
Browse and download past year exam papers.

Tables used
───────────
parent_chunks  – RAG chunks (one row per exam question); already exists.
exam_papers    – One row per paper PDF; created here if absent.

Endpoints
─────────
GET  /subjects                                  list distinct subject codes
GET  /papers                                    browse papers (with PDF availability)
GET  /papers/{course_code}/{year}/{semester}    all questions for one paper
GET  /papers/{course_code}/{year}/{semester}/download   signed PDF download URL
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from core.security import get_current_user
from core.database import execute_query, execute_write

router = APIRouter()


# ── Bootstrap exam_papers table ───────────────────────────────────────────────

def _ensure_exam_papers_table() -> None:
    execute_write("""
        CREATE TABLE IF NOT EXISTS exam_papers (
            id           SERIAL PRIMARY KEY,
            course_code  VARCHAR(20)  NOT NULL,
            subject_name VARCHAR(255) DEFAULT '',
            year         INT          NOT NULL,
            semester     VARCHAR(100) NOT NULL,
            pdf_path     TEXT         NOT NULL,
            file_size_kb INT          DEFAULT 0,
            uploaded_at  TIMESTAMP    DEFAULT NOW(),
            UNIQUE (course_code, year, semester)
        );
    """)

_ensure_exam_papers_table()


# ── /subjects ─────────────────────────────────────────────────────────────────

@router.get("/subjects")
def list_subjects(current_user: dict = Depends(get_current_user)):
    """
    All distinct course codes.  Includes subject_name if one has been
    registered in exam_papers; falls back to the course code itself.
    """
    rows = execute_query("""
        SELECT
            pc.course_code,
            COALESCE(MAX(ep.subject_name), '') AS subject_name
        FROM   parent_chunks pc
        LEFT JOIN exam_papers ep ON ep.course_code = pc.course_code
        GROUP  BY pc.course_code
        ORDER  BY pc.course_code;
    """)
    return [
        {"course_code": r[0], "subject_name": r[1] or r[0]}
        for r in (rows or [])
    ]


# ── /papers ───────────────────────────────────────────────────────────────────

@router.get("/papers")
def list_papers(
    course_code:  Optional[str] = Query(None),
    year:         Optional[int] = Query(None),
    semester:     Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Browse available papers.  Returns one row per (course_code, year, semester)
    combination, joined with exam_papers so the frontend knows whether a PDF
    is available for download.
    """
    conditions = ["1=1"]
    params: list = []

    if course_code:
        conditions.append("pc.course_code = %s")
        params.append(course_code)
    if year:
        conditions.append("pc.year = %s")
        params.append(year)
    if semester:
        conditions.append("pc.semester = %s")
        params.append(semester)

    where = " AND ".join(conditions)

    rows = execute_query(f"""
        SELECT
            pc.course_code,
            pc.semester,
            pc.year,
            COUNT(*)                                              AS total_questions,
            SUM(pc.total_marks)                                   AS total_marks,
            COUNT(CASE WHEN pc.image_urls != '{{}}' THEN 1 END)  AS questions_with_images,
            COALESCE(MAX(ep.subject_name), '')                    AS subject_name,
            MAX(ep.pdf_path)                                      AS pdf_path,
            MAX(ep.file_size_kb)                                  AS file_size_kb
        FROM   parent_chunks pc
        LEFT JOIN exam_papers ep
               ON ep.course_code = pc.course_code
              AND ep.year        = pc.year
              AND ep.semester    = pc.semester
        WHERE  {where}
        GROUP  BY pc.course_code, pc.semester, pc.year
        ORDER  BY pc.course_code, pc.year DESC, pc.semester;
    """, params or None)

    return [
        {
            "course_code":           r[0],
            "semester":              r[1],
            "year":                  r[2],
            "total_questions":       r[3],
            "total_marks":           r[4],
            "questions_with_images": r[5],
            "subject_name":          r[6] or r[0],
            "has_pdf":               r[7] is not None,
            "file_size_kb":          r[8] or 0,
        }
        for r in (rows or [])
    ]


# ── /papers/{code}/{year}/{sem} ───────────────────────────────────────────────

@router.get("/papers/{course_code}/{year}/{semester}")
def get_paper_questions(
    course_code:  str,
    year:         int,
    semester:     str,
    current_user: dict = Depends(get_current_user),
):
    """All questions for a specific paper (used by the detail modal)."""
    semester = semester.replace("%20", " ")

    rows = execute_query("""
        SELECT parent_id, question_number, full_text, total_marks,
               children, image_urls
        FROM   parent_chunks
        WHERE  course_code = %s AND year = %s AND semester = %s
        ORDER  BY question_number::int;
    """, (course_code, year, semester))

    if not rows:
        raise HTTPException(status_code=404, detail="Paper not found")

    return {
        "course_code": course_code,
        "semester":    semester,
        "year":        year,
        "questions": [
            {
                "parent_id":       r[0],
                "question_number": r[1],
                "full_text":       r[2],
                "total_marks":     r[3],
                "children":        r[4],
                "image_urls":      r[5] or {},
            }
            for r in rows
        ],
    }


# ── /papers/{code}/{year}/{sem}/download ─────────────────────────────────────

@router.get("/papers/{course_code}/{year}/{semester}/download")
def download_paper(
    course_code:  str,
    year:         int,
    semester:     str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return a 1-hour signed URL for the paper PDF stored in Supabase Storage.
    The frontend opens this URL directly — no streaming through the API.
    """
    semester = semester.replace("%20", " ")

    row = execute_query("""
        SELECT pdf_path, subject_name, file_size_kb
        FROM   exam_papers
        WHERE  course_code = %s AND year = %s AND semester = %s
        LIMIT  1;
    """, (course_code, year, semester), fetch="one")

    if not row:
        raise HTTPException(
            status_code=404,
            detail="PDF not available for this paper yet."
        )

    pdf_path, subject_name, file_size_kb = row

    from services.storage import create_signed_url
    try:
        signed_url = create_signed_url(pdf_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    filename = f"{course_code}_{semester.replace(' ', '_')}_{year}.pdf"

    return {
        "url":          signed_url,
        "filename":     filename,
        "subject_name": subject_name,
        "file_size_kb": file_size_kb,
        "expires_in":   3600,
    }

@router.get("/papers/{course_code}/topics")
def get_topic_frequency(
    course_code: str,
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Aggregates question topics across papers for a subject.
    Returns per-question frequency and which semesters it appeared in.
    """
    conditions = ["course_code = %s"]
    params = [course_code]
    if year:
        conditions.append("year = %s")
        params.append(year)

    where = " AND ".join(conditions)

    rows = execute_query(f"""
        SELECT
            question_number,
            COUNT(*)                            AS appearances,
            array_agg(DISTINCT year ORDER BY year DESC) AS years,
            array_agg(DISTINCT semester)        AS semesters,
            -- grab the full_text from the most recent paper
            (array_agg(full_text ORDER BY year DESC, semester DESC))[1] AS sample_text
        FROM parent_chunks
        WHERE {where}
        GROUP BY question_number
        ORDER BY question_number::int;
    """, params)

    return {
        "course_code": course_code,
        "topics": [
            {
                "question_number": r[0],
                "appearances":     r[1],
                "years":           r[2],
                "semesters":       r[3],
                "sample_text":     r[4],
            }
            for r in (rows or [])
        ]
    }