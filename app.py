# filename: tracker_app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# ------------------ Config ------------------
# Streamlit Secrets: {"NEON_CONN": "<your_neon_conn_string>"}
def get_conn():
    return psycopg2.connect(st.secrets["NEON_CONN"])

# ------------------ DB Init ------------------
def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    # Keyword mapping table
    c.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL REFERENCES users(username),
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            UNIQUE(username, keyword)
        )
    """)
    # Logs table
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL REFERENCES users(username),
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ------------------ Auth ------------------
if "user" not in st.session_state:
    st.session_state.user = None

def signup(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        st.session_state.user = username  # auto-login after signup
        st.success(f"✅ Signed up and logged in as {username}")
    except psycopg2.errors.UniqueViolation:
        st.error("⚠️ Username already exists")
    finally:
        conn.close()

def login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=%s", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == password:
        st.session_state.user = username
        st.success(f"✅ Logged in as {username}")
    else:
        st.error("❌ Invalid username or password")

def logout():
    st.session_state.user = None
    st.success("Logged out successfully")

# ------------------ Main App ------------------
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")
st.title("📊 Daily Activity Tracker")

# ------------------ Login / Signup UI ------------------
if st.session_state.user is None:
    st.subheader("Login / Signup")
    col1, col2 = st.columns(2)
    with col1:
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            login(login_user, login_pass)
    with col2:
        signup_user = st.text_input("New Username", key="signup_user")
        signup_pass = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Signup"):
            signup(signup_user, signup_pass)
    st.stop()  # Stop app until logged in

# ------------------ Logout Button ------------------
st.sidebar.button("Logout", on_click=logout)

# ------------------ Logging Function ------------------
def log_entry(prompt):
    conn = get_conn()
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        # insert or update mapping
        c.execute("""
            INSERT INTO keyword_mapping (username, keyword, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (username, keyword) DO UPDATE SET category=EXCLUDED.category
        """, (st.session_state.user, keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("""
            SELECT category FROM keyword_mapping WHERE username=%s AND keyword=%s
        """, (st.session_state.user, keyword))
        row = c.fetchone()
        category = row[0] if row else None

    if category:
        c.execute("""
            INSERT INTO logs (username, keyword, category, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (st.session_state.user, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# ------------------ Sidebar Filters ------------------
st.sidebar.header("Filters")
conn = get_conn()
c = conn.cursor()
c.execute("SELECT DISTINCT category FROM logs WHERE username=%s", (st.session_state.user,))
categories = [row[0] for row in c.fetchall()]
conn.close()
selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

# ------------------ Input ------------------
prompt = st.text_input("Enter a keyword (or 'keyword = category'):")
if st.button("Submit") and prompt:
    result = log_entry(prompt)
    st.success(result)

# ------------------ Display Logs ------------------
conn = get_conn()
c = conn.cursor()
if selected_category == "All":
    c.execute("SELECT keyword, category, timestamp FROM logs WHERE username=%s ORDER BY timestamp DESC LIMIT 50", (st.session_state.user,))
else:
    c.execute("SELECT keyword, category, timestamp FROM logs WHERE username=%s AND category=%s ORDER BY timestamp DESC LIMIT 50", (st.session_state.user, selected_category))
rows = c.fetchall()
logs_df = pd.DataFrame(rows, columns=["keyword", "category", "timestamp"])
conn.close()

if not logs_df.empty:
    st.subheader("📝 Recent Logs")
    st.dataframe(logs_df)
else:
    st.info("No logs yet.")

# ------------------ Display Keyword Mappings ------------------
conn = get_conn()
c = conn.cursor()
c.execute("SELECT keyword, category FROM keyword_mapping WHERE username=%s ORDER BY keyword", (st.session_state.user,))
rows = c.fetchall()
mapping_df = pd.DataFrame(rows, columns=["keyword", "category"])
conn.close()

if not mapping_df.empty:
    st.subheader("📚 Keyword Mappings")
    st.dataframe(mapping_df)
