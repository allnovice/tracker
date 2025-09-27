# filename: tracker.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# --- Streamlit config ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")
st.title("📊 Daily Activity Tracker")

# --- Neon / PostgreSQL connection ---
conn_str = st.secrets["NEON_CONN"]

def get_conn():
    return psycopg2.connect(conn_str)

# --- Functions ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    ''')
    conn.commit()
    conn.close()

def log_entry(prompt):
    conn = get_conn()
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("""
            INSERT INTO keyword_mapping (keyword, category)
            VALUES (%s, %s)
            ON CONFLICT (keyword) DO UPDATE SET category = EXCLUDED.category
        """, (keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE keyword=%s", (keyword,))
        row = c.fetchone()
        if row:
            category = row[0]
        else:
            category = None

    if category:
        c.execute("INSERT INTO logs (keyword, category, timestamp) VALUES (%s, %s, %s)",
                  (keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Initialize DB ---
init_db()

# --- Sidebar filter ---
st.sidebar.header("Filters")
conn = get_conn()
categories = [row[0] for row in pd.read_sql("SELECT DISTINCT category FROM logs", conn).values]
conn.close()
selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

# --- Input ---
prompt = st.text_input("Enter a keyword (or 'keyword = category'):")

if st.button("Submit") and prompt:
    result = log_entry(prompt)
    st.success(result)

# --- Display logs ---
conn = get_conn()
if selected_category == "All":
    logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs ORDER BY timestamp DESC LIMIT 50", conn)
else:
    logs_df = pd.read_sql(
        "SELECT keyword, category, timestamp FROM logs WHERE category=%s ORDER BY timestamp DESC LIMIT 50",
        conn, params=(selected_category,)
    )
conn.close()

if not logs_df.empty:
    st.subheader("📝 Recent Logs")
    st.dataframe(logs_df)
else:
    st.info("No logs yet.")

# --- Keyword mapping ---
conn = get_conn()
mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
conn.close()

if not mapping_df.empty:
    st.subheader("📚 Keyword Mappings")
    st.dataframe(mapping_df)
