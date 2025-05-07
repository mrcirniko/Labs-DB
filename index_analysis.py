import os
import psycopg2
import time
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "db")
DB_PORT = os.getenv("POSTGRES_PORT", 5432)

QUERIES = {
    "category_btree": "SELECT COUNT(*) FROM resumes WHERE category = 'Data Science';",
    "resume_trgm": "SELECT COUNT(*) FROM resumes WHERE resume ILIKE '%python%';",
    "resume_gin": "SELECT COUNT(*) FROM resumes WHERE tsv_resume @@ plainto_tsquery('english', 'python');"
}

def connect():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

def drop_indexes_and_column():
    with connect() as conn:
        conn.autocommit = True
        cur = conn.cursor()
        print("Удаление индексов и tsv_resume...")
        cur.execute("DROP INDEX IF EXISTS idx_category_btree;")
        cur.execute("DROP INDEX IF EXISTS idx_resume_trgm;")
        cur.execute("DROP INDEX IF EXISTS idx_resume_gin;")
        cur.execute("DROP INDEX IF EXISTS idx_resume_brin;")
        cur.execute("ALTER TABLE resumes DROP COLUMN IF EXISTS tsv_resume;")

def create_indexes():
    with connect() as conn:
        conn.autocommit = True
        cur = conn.cursor()
        print("Создание индексов и колонки tsv_resume...")
        cur.execute("""
            ALTER TABLE resumes
            ADD COLUMN tsv_resume tsvector GENERATED ALWAYS AS (to_tsvector('english', resume)) STORED;
        """)
        cur.execute("CREATE INDEX idx_category_btree ON resumes(category);")
        cur.execute("CREATE INDEX idx_resume_trgm ON resumes USING gin (resume gin_trgm_ops);")
        cur.execute("CREATE INDEX idx_resume_gin ON resumes USING gin(tsv_resume);")
        cur.execute("CREATE INDEX idx_resume_brin ON resumes USING brin(id);")

def measure_query_time(cur, query):
    start = time.time()
    cur.execute(query)
    cur.fetchone()
    return time.time() - start

def main():
    drop_indexes_and_column()

    print("\n== Измерение до индексов ==")
    before = {}
    with connect() as conn:
        conn.autocommit = True
        cur = conn.cursor()
        for name, query in QUERIES.items():
            try:
                before[name] = measure_query_time(cur, query)
            except Exception as e:
                before[name] = float('nan')
                print(f"{name}: ошибка выполнения до индекса — {e}")

    create_indexes()

    print("\n== Измерение после индексов ==")
    after = {}
    with connect() as conn:
        conn.autocommit = True
        cur = conn.cursor()
        for name, query in QUERIES.items():
            after[name] = measure_query_time(cur, query)

    print("\n== Сравнение времени выполнения (сек) ==")
    for name in QUERIES:
        b, a = before.get(name, float('nan')), after[name]
        speedup = b / a if isinstance(b, float) and b > 0 else 0
        print(f"{name:15}: до = {b:.4f}, после = {a:.4f}, ускорение: x{speedup:.1f}")

if __name__ == "__main__":
    main()
