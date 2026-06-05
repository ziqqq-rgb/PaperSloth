import os, re, fitz, psycopg2
from psycopg2.extras import Json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

BUCKET = "exam-images"
sb     = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
DB_URL = os.getenv("DATABASE_URL")

PDF_MAP = {
    ("EDB2613", "September 2022",          2022): "data/papers/inc sept2022.pdf",
    ("EDB2613", "MAY 2022 SEMESTER",        2022): "data/papers/inc may2022.pdf",
    ("EDB2613", "JANUARY 2023 SEMESTER",    2023): "data/papers/inc jan2023.pdf",
    ("EDB2613", "MAY 2023 SEMESTER",        2023): "data/papers/inc may2023.pdf",
    ("EDB2613", "SEPTEMBER 2023 SEMESTER",  2023): "data/papers/inc sept2023.pdf",
    ("EDB2613", "MAY 2024 SEMESTER",        2024): "data/papers/inc may2024.pdf",
    ("RBB3013", "January 2024",             2024): "data/papers/inc jan 2024.pdf",
    ("RBB3013", "SEPTEMBER 2024 SEMESTER",  2024): "data/papers/inc sept2024.pdf",
    ("RBB3013", "JANUARY 2025 SEMESTER",    2025): "data/papers/inc jan2025.pdf",
    ("RBB3013", "May 2025",                 2025): "data/papers/inc may2025.pdf",
    ("RBB3013", "September 2025",           2025): "data/papers/inc sept2025.pdf",
}

conn = psycopg2.connect(DB_URL)
cur  = conn.cursor()

cur.execute("""
    SELECT parent_id, question_number, image_urls, course_code, semester, year
    FROM   parent_chunks
    WHERE  image_urls != '{}'
    ORDER  BY course_code, year, semester
""")
rows = cur.fetchall()
print(f"Found {len(rows)} parents with images\n")

for parent_id, qnum, image_urls, course_code, semester, year in rows:
    key      = (course_code, semester, year)
    pdf_path = PDF_MAP.get(key)

    if not pdf_path:
        print(f"⚠️  No PDF mapped for {key}")
        continue
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF not found: {pdf_path}")
        continue

    pdf_doc  = fitz.open(pdf_path)
    new_urls = {}

    for label, old_url in image_urls.items():
        match = re.search(r'/object/public/exam-images/(.+)$', old_url)
        if not match:
            print(f"  ⚠️  Can't parse path from: {old_url}")
            new_urls[label] = old_url
            continue

        storage_path = match.group(1)
        qnum_str     = str(qnum)
        label_clean  = label.replace(" ", "").upper()
        target_page  = None

        # Pass 1 — exact label text match
        for page_no in range(len(pdf_doc)):
            if label_clean in pdf_doc[page_no].get_text().replace(" ", "").upper():
                target_page = page_no
                break

        # Pass 2 — page contains FIGURE/TABLE + question number
        if target_page is None:
            for page_no in range(len(pdf_doc)):
                text = pdf_doc[page_no].get_text().upper()
                if ("FIGURE" in text or "TABLE" in text) and f"Q{qnum_str}" in text:
                    target_page = page_no
                    break

        # Pass 3 — best match by question number mentions
        if target_page is None:
            best_page, best_count = 0, 0
            for page_no in range(len(pdf_doc)):
                text  = pdf_doc[page_no].get_text().upper()
                count = text.count(f"Q{qnum_str}") + text.count(f"QUESTION {qnum_str}")
                if count > best_count:
                    best_count = count
                    best_page  = page_no
            target_page = best_page
            print(f"  ℹ️  Best-match page {target_page + 1} for '{label}'")

        # Render page
        pix       = pdf_doc[target_page].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img_bytes = pix.tobytes("png")

        try:
            # supabase-py v2 upload syntax
            sb.storage.from_(BUCKET).upload(
                path    = storage_path,
                file    = img_bytes,
                file_options = {
                    "content-type": "image/png",
                    "upsert":       "true",
                }
            )

            # v2 get_public_url returns a string directly
            raw_url   = sb.storage.from_(BUCKET).get_public_url(storage_path)
            clean_url = str(raw_url).replace("/rest/v1/storage/", "/storage/")

            new_urls[label] = clean_url
            print(f"  ✅ {label} → page {target_page + 1} → {clean_url}")

        except Exception as e:
            err = str(e)
            if "already exists" in err or "Duplicate" in err:
                # File already uploaded — just fix the URL
                raw_url         = sb.storage.from_(BUCKET).get_public_url(storage_path)
                clean_url       = str(raw_url).replace("/rest/v1/storage/", "/storage/")
                new_urls[label] = clean_url
                print(f"  ♻️  Already exists, URL fixed: {label}")
            else:
                print(f"  ❌ Upload failed for {label}: {e}")
                new_urls[label] = old_url

    cur.execute(
        "UPDATE parent_chunks SET image_urls = %s WHERE parent_id = %s",
        (Json(new_urls), parent_id)
    )
    conn.commit()
    pdf_doc.close()
    print(f"  💾 Saved {parent_id}\n")

cur.close()
conn.close()
print("✅ All done — restart your backend")