# filename: tracker.py
import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

DB_FILE = "logs.db"

# Initialize DB
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Function to log keyword
def log_entry(prompt):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("INSERT OR REPLACE INTO keyword_mapping (keyword, category) VALUES (?, ?)", (keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE keyword=?", (keyword,))
        row = c.fetchone()
        if row:
            category = row[0]
        else:
            category = None

    if category:
        c.execute("INSERT INTO logs (keyword, category, timestamp) VALUES (?, ?, ?)",
                  (keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit UI ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")
st.title("📊 Daily Activity Tracker")

# Sidebar filter
st.sidebar.header("Filters")
conn = sqlite3.connect(DB_FILE)
categories = [row[0] for row in conn.execute("SELECT DISTINCT category FROM logs").fetchall()]
conn.close()
selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

# Input
prompt = st.text_input("Enter a keyword (or 'keyword = category'):")

if st.button("Submit") and prompt:
    result = log_entry(prompt)
    st.success(result)

# Display logs
conn = sqlite3.connect(DB_FILE)
if selected_category == "All":
    logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs ORDER BY timestamp DESC LIMIT 50", conn)
else:
    logs_df = pd.read_sql(f"SELECT keyword, category, timestamp FROM logs WHERE category='{selected_category}' ORDER BY timestamp DESC LIMIT 50", conn)
conn.close()

if not logs_df.empty:
    st.subheader("📝 Recent Logs")
    st.dataframe(logs_df)
else:
    st.info("No logs yet.")

# Optional: show category mapping
conn = sqlite3.connect(DB_FILE)
mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
conn.close()
if not mapping_df.empty:
    st.subheader("📚 Keyword Mappings")
    st.dataframe(mapping_df)
