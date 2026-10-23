import os
from psycopg.rows import dict_row
from dotenv import load_dotenv
from contextlib import contextmanager
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set (check .env)")

pool = ConnectionPool(conninfo=DATABASE_URL, open=False, kwargs={"row_factory": dict_row})

def open_pool():  
    pool.open()

def close_pool():
    pool.close()

@contextmanager
def get_connection():
    connection = pool.getconn()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        pool.putconn(connection)