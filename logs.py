import psycopg2
from datetime import datetime
import os

def get_conn():
    db_url = os.environ.get("NEON")
    return psycopg2.connect(db_url)

# Lazy table creation
def init_tables():
    conn = get_conn()
    cur = conn.cursor()
    # keyword -> category mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            UNIQUE(username, keyword)
        )
    """)
    # logs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_entry(username, prompt):
    init_tables()  # ensure tables exist

    conn = get_conn()
    cur = conn.cursor()
    message = ""

    if "=" in prompt:  # user defines category explicitly
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        cur.execute("""
            INSERT INTO keyword_mapping (username, keyword, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (username, keyword)
            DO UPDATE SET category = EXCLUDED.category
        """, (username, keyword, category))
    else:
        keyword = prompt.strip().lower()
        cur.execute("""
            SELECT category FROM keyword_mapping
            WHERE username = %s AND keyword = %s
        """, (username, keyword))
        row = cur.fetchone()
        category = row[0] if row else None

    if category:
        cur.execute("""
            INSERT INTO logs (username, keyword, category, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (username, keyword, category, datetime.now()))
        message = f"✅ Logged '{keyword}' under '{category}'"
    else:
        message = f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

    conn.commit()
    conn.close()
    return message
