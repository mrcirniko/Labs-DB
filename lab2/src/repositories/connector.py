import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from contextlib import contextmanager
from settings import DB_CONFIG, POOL_MIN_CONN, POOL_MAX_CONN
import atexit

# Функция для проверки подключения
def test_db_connection():
    try:
        with connection_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                print("✅ Successfully connected to the database.")
    except OperationalError as e:
        print(f"❌ Failed to connect to the database: {e}")
    finally:
        connection_pool.putconn(conn)

print("Initializing connection pool...")
try:
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        POOL_MIN_CONN, POOL_MAX_CONN, **DB_CONFIG
    )
    if connection_pool:
        test_db_connection()
except OperationalError as e:
    print(f"❌ Error during pool creation: {e}")
    connection_pool = None

@contextmanager
def get_connection():
    if not connection_pool:
        raise Exception("Connection pool is not initialized.")
    connection = connection_pool.getconn()
    try:
        yield connection
    finally:
        connection_pool.putconn(connection)

def close_connection_pool():
    if connection_pool:
        connection_pool.closeall()
        print("Connection pool closed.")

atexit.register(close_connection_pool)
