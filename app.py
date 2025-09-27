# filename: tracker_neon.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# --- Connect to Neon ---
conn_str = st.secrets["NEON_CONN"]

def get_conn():
    return psycopg2.connect(conn_str)

# --- Initialize DB ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Optional keyword mapping
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Helper functions ---
def signup(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        st.session_state["user"] = username  # auto-login
        return True, "Signup successful! Logged in."
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "Username already exists."
    finally:
        conn.close()

def login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        st.session_state["user"] = username
        return True, f"Welcome back, {username}!"
    return False, "Invalid username or password."

def log_entry(username, prompt):
    conn = get_conn()
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("INSERT INTO keyword_mapping (keyword, category) VALUES (%s, %s) ON CONFLICT (keyword) DO UPDATE SET category=EXCLUDED.category", (keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE keyword=%s", (keyword,))
        row = c.fetchone()
        category = row[0] if row else None

    if category:
        c.execute("INSERT INTO logs (username, keyword, category) VALUES (%s, %s, %s)", (username, keyword, category))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit UI ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")

if "user" not in st.session_state:
    st.session_state["user"] = None

if not st.session_state["user"]:
    st.title("Login or Signup")
    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        l_user = st.text_input("Username", key="l_user")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login"):
            success, msg = login(l_user, l_pass)
            st.success(msg) if success else st.error(msg)

    with tab2:
        s_user = st.text_input("Username", key="s_user")
        s_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Signup"):
            success, msg = signup(s_user, s_pass)
            st.success(msg) if success else st.error(msg)

else:
    st.title(f"📊 Daily Activity Tracker - {st.session_state['user']}")
    prompt = st.text_input("Enter a keyword (or 'keyword = category'):")

    if st.button("Submit") and prompt:
        result = log_entry(st.session_state["user"], prompt)
        st.success(result)

    # Sidebar filter
    st.sidebar.header("Filters")
    conn = get_conn()
    categories = [row[0] for row in conn.cursor().execute("SELECT DISTINCT category FROM logs WHERE username=%s", (st.session_state["user"],))]
    conn.close()
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

    # Display logs
    conn = get_conn()
    if selected_category == "All":
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s ORDER BY timestamp DESC LIMIT 50", conn, params=(st.session_state["user"],))
    else:
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s AND category=%s ORDER BY timestamp DESC LIMIT 50", conn, params=(st.session_state["user"], selected_category))
    conn.close()

    if not logs_df.empty:
        st.subheader("📝 Recent Logs")
        st.dataframe(logs_df)
    else:
        st.info("No logs yet.")

    # Optional: keyword mappings
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
