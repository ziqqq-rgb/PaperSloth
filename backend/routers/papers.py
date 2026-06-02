from typing import Optional
from fastapi import APIRouter, Depends, Query

from core.security import get_current_user
from core.database import execute_query

router = APIRouter()


@router.get("/subjects")
def list_subjects(current_user: dict = Depends(get_current_user)):
    """
    Return all distinct subjects available in the system.
    Used to populate the subject dropdown in the browse UI.
    """
    rows = execute_query("""
        SELECT DISTINCT course_code, MIN(semester) as sample_semester
        FROM   parent_chunks
        GROUP  BY course_code
        ORDER  BY course_code;
    """)
    return [{"course_code": r[0]} for r in (rows or [])]


@router.get("/papers")
def list_papers(
    course_code:  Optional[str] = Query(None),
    year:         Optional[int] = Query(None),
    semester:     Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Browse available papers with optional filters.
    Returns one row per (course_code, semester, year) combination.
    """
    conditions = ["1=1"]
    params     = []

    if course_code:
        conditions.append("course_code = %s")
        params.append(course_code)
    if year:
        conditions.append("year = %s")
        params.append(year)
    if semester:
        conditions.append("semester = %s")
        params.append(semester)

    where = " AND ".join(conditions)

    rows = execute_query(f"""
        SELECT course_code, semester, year,
               COUNT(*)                         AS total_questions,
               SUM(total_marks)                 AS total_marks,
               COUNT(CASE WHEN image_urls != '{{}}' THEN 1 END) AS questions_with_images
        FROM   parent_chunks
        WHERE  {where}
        GROUP  BY course_code, semester, year
        ORDER  BY course_code, year DESC, semester;
    """, params or None)

    return [
        {
            "course_code":             r[0],
            "semester":                r[1],
            "year":                    r[2],
            "total_questions":         r[3],
            "total_marks":             r[4],
            "questions_with_images":   r[5],
        }
        for r in (rows or [])
    ]


@router.get("/papers/{course_code}/{year}/{semester}")
def get_paper_questions(
    course_code:  str,
    year:         int,
    semester:     str,
    current_user: dict = Depends(get_current_user),
):
    """
    Return all questions for a specific paper.
    Used when a student requests a full past year paper.
    """
    # URL-encode spaces in semester, e.g. "September%202025" → "September 2025"
    semester = semester.replace("%20", " ")

    rows = execute_query("""
        SELECT parent_id, question_number, full_text, total_marks,
               children, image_urls
        FROM   parent_chunks
        WHERE  course_code = %s AND year = %s AND semester = %s
        ORDER  BY question_number::int;
    """, (course_code, year, semester))

    if not rows:
        from fastapi import HTTPException
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