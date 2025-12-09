import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")  # Vem do Vercel

engine = create_engine(DATABASE_URL, future=True)

def query(sql, params=None):
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {})
