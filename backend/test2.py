import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SELECT image_urls FROM parent_chunks WHERE image_urls != '{}' LIMIT 3")
for row in cur.fetchall():
    print(row[0])