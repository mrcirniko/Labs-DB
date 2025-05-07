import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from time import sleep

user = os.getenv("POSTGRES_USER")
password = os.getenv("POSTGRES_PASSWORD")
db = os.getenv("POSTGRES_DB")
csv_path = os.getenv("CSV_PATH")
host = os.getenv("POSTGRES_HOST", "db")

sleep(10)
print("Launch load_data.py...")
try:
    print("Connecting to database...")
    conn = psycopg2.connect(
        dbname=db,
        user=user,
        password=password,
        host=host,
        port=5432
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Dropping old table and creating new one...")
    cur.execute("DROP TABLE IF EXISTS resumes;")
    cur.execute("""
        CREATE TABLE resumes (
            id SERIAL PRIMARY KEY,
            category TEXT,
            resume TEXT
        );
    """)

    print("Loading CSV:", csv_path)
    df = pd.read_csv(csv_path)
    print("Loaded CSV with", len(df), "rows")

    print("Inserting data...")
    records = df.to_records(index=False)
    values = list(records)

    insert_query = """
        INSERT INTO resumes (category, resume)
        VALUES %s
    """
    execute_values(cur, insert_query, values, page_size=5000)
    print("Insert done.")

    cur.close()
    conn.close()
    print("Done.")

except Exception as e:
    print("ERROR:", e)
