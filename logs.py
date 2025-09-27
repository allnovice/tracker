# logs.py
import psycopg2
from datetime import datetime
import os

# Connect to Neon DB
def get_conn():
    db_url = os.environ.get("NEON")
    return psycopg2.connect(db_url)

# Initialize tables
def init_tables():
    conn = get_conn()
    cur = conn.cursor()
    
    # Table for keyword -> category mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            UNIQUE(username, keyword)
        )
    """)
    
    # Table for logs
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

init_tables()

# Log entry function
def log_entry(username, prompt):
    conn = get_conn()
    cur = conn.cursor()
    message = ""

    # If user defines category explicitly
    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        # Insert or update mapping
        cur.execute("""
            INSERT INTO keyword_mapping (username, keyword, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (username, keyword) DO UPDATE SET category = EXCLUDED.category
        """, (username, keyword, category))
    else:
        keyword = prompt.strip().lower()
        # Look up category
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
