# filename: tracker_app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- DB Connection ---
def get_conn():
    conn_str = st.secrets["NEON_CONN"]
    return psycopg2.connect(conn_str)

# --- Initialize DB (first run only) ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    # Logs table with username
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Keyword mapping table
    c.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Authentication ---
def signup(user, pwd):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (user, pwd))
        conn.commit()
        conn.close()
        st.session_state.user = user
        return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return False

def login(user, pwd):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (user, pwd))
    row = c.fetchone()
    conn.close()
    if row:
        st.session_state.user = user
        return True
    return False

def logout():
    if "user" in st.session_state:
        del st.session_state.user

# --- Logging Function ---
def log_entry(user, prompt):
    conn = get_conn()
    c = conn.cursor()
    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("INSERT INTO keyword_mapping (keyword, category) VALUES (%s, %s) ON CONFLICT (keyword) DO UPDATE SET category=EXCLUDED.category", (keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE keyword=%s", (keyword,))
        row = c.fetchone()
        if row:
            category = row[0]
        else:
            category = None
    if category:
        c.execute("INSERT INTO logs (username, keyword, category, timestamp) VALUES (%s, %s, %s, %s)",
                  (user, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit UI ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

# --- Login / Signup ---
if st.session_state.user is None:
    st.title("🔑 Login / Signup")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Login")
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login(login_user, login_pass):
                st.success(f"Logged in as {login_user}")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")

    with col2:
        st.subheader("Signup")
        signup_user = st.text_input("New Username", key="signup_user")
        signup_pass = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Signup"):
            if signup(signup_user, signup_pass):
                st.success(f"Account created. Logged in as {signup_user}")
                st.experimental_rerun()
            else:
                st.error("Username already exists")
else:
    st.title(f"📊 Daily Activity Tracker - {st.session_state.user}")
    if st.button("Logout"):
        logout()
        st.experimental_rerun()

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM logs WHERE username=%s", (st.session_state.user,))
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

    # --- Input ---
    prompt = st.text_input("Enter a keyword (or 'keyword = category'):")
    if st.button("Submit") and prompt:
        result = log_entry(st.session_state.user, prompt)
        st.success(result)

    # --- Display Logs ---
    conn = get_conn()
    if selected_category == "All":
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s ORDER BY timestamp DESC LIMIT 50", conn, params=(st.session_state.user,))
    else:
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s AND category=%s ORDER BY timestamp DESC LIMIT 50", conn, params=(st.session_state.user, selected_category))
    conn.close()

    if not logs_df.empty:
        st.subheader("📝 Recent Logs")
        st.dataframe(logs_df)
    else:
        st.info("No logs yet.")

    # --- Keyword Mapping ---
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
