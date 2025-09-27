# tracker.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- Database connection ---
def get_conn():
    conn_str = st.secrets["NEON_CONN"]
    return psycopg2.connect(conn_str)

# --- Initialize DB ---
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

# --- Helper functions ---
def signup(username, password):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        conn.close()
        return True, "✅ Signup successful."
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return False, "⚠️ Username already exists."

def login(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    conn.close()
    if row and row[0] == password:
        return True
    return False

def log_entry(username, prompt):
    conn = get_conn()
    cur = conn.cursor()
    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        cur.execute("""
            INSERT INTO keyword_mapping (username, keyword, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (keyword) DO UPDATE SET category = EXCLUDED.category;
        """, (username, keyword, category))
    else:
        keyword = prompt.strip().lower()
        cur.execute("SELECT category FROM keyword_mapping WHERE username=%s AND keyword=%s", (username, keyword))
        row = cur.fetchone()
        category = row[0] if row else None

    if category:
        cur.execute("INSERT INTO logs (username, keyword, category, timestamp) VALUES (%s,%s,%s,%s)",
                    (username, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit UI ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")
st.title("📊 Daily Activity Tracker")

# --- Session management ---
if "user" not in st.session_state:
    st.session_state.user = None
if "login_msg" not in st.session_state:
    st.session_state.login_msg = ""

# --- Login / Signup ---
if st.session_state.user is None:
    tab1, tab2 = st.tabs(["Login", "Signup"])
    with tab1:
        username_input = st.text_input("Username", key="login_user")
        password_input = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login(username_input, password_input):
                st.session_state.user = username_input
                st.session_state.login_msg = "✅ Logged in successfully."
                st.experimental_rerun()
            else:
                st.session_state.login_msg = "⚠️ Invalid credentials."
        if st.session_state.login_msg:
            st.info(st.session_state.login_msg)

    with tab2:
        new_user = st.text_input("New Username", key="signup_user")
        new_pass = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Signup"):
            success, msg = signup(new_user, new_pass)
            st.info(msg)
            if success:
                st.session_state.user = new_user
                st.experimental_rerun()

# --- Logged in UI ---
else:
    username = st.session_state.user
    st.sidebar.markdown(f"**Logged in as:** {username}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.experimental_rerun()

    # --- Sidebar filter ---
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM logs WHERE username=%s", (username,))
    categories = [row[0] for row in cur.fetchall()]
    conn.close()
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

    # --- Input ---
    prompt = st.text_input("Enter a keyword (or 'keyword = category'):")
    if st.button("Submit") and prompt:
        result = log_entry(username, prompt)
        st.success(result)

    # --- Display logs ---
    conn = get_conn()
    if selected_category == "All":
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s ORDER BY timestamp DESC LIMIT 50",
                              conn, params=(username,))
    else:
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s AND category=%s ORDER BY timestamp DESC LIMIT 50",
                              conn, params=(username, selected_category))
    conn.close()

    if not logs_df.empty:
        st.subheader("📝 Recent Logs")
        st.dataframe(logs_df)
    else:
        st.info("No logs yet.")

    # --- Optional: show category mapping ---
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping WHERE username=%s ORDER BY keyword",
                             conn, params=(username,))
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
