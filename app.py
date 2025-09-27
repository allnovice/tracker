# filename: app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- Streamlit page setup ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")

# --- Neon/Postgres connection ---
def get_conn():
    conn_str = st.secrets["NEON_CONN"]
    return psycopg2.connect(conn_str)

# --- Initialize DB tables ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    # Logs table with username
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Keyword mapping table
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            keyword TEXT PRIMARY KEY,
            category TEXT NOT NULL
        )
    ''')
    conn.commit()
    c.close()
    conn.close()

init_db()

# --- Helper functions ---
def signup(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username=%s", (username,))
    if c.fetchone():
        conn.close()
        return False, "Username already exists."
    c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
    conn.commit()
    conn.close()
    return True, "Signup successful!"

def login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=%s", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == password:
        return True
    return False

def log_entry(username, prompt):
    conn = get_conn()
    c = conn.cursor()
    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("INSERT INTO keyword_mapping (keyword, category) VALUES (%s, %s) ON CONFLICT (keyword) DO UPDATE SET category = EXCLUDED.category", (keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE keyword=%s", (keyword,))
        row = c.fetchone()
        if row:
            category = row[0]
        else:
            category = None

    if category:
        c.execute("INSERT INTO logs (username, keyword, category, timestamp) VALUES (%s, %s, %s, %s)", (username, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Session state ---
if "user" not in st.session_state:
    st.session_state.user = None

# --- Authentication UI ---
if st.session_state.user is None:
    st.title("🔐 Login / Signup")
    auth_tab = st.tabs(["Login", "Signup"])

    with auth_tab[0]:
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login(login_user, login_pass):
                st.session_state.user = login_user
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with auth_tab[1]:
        signup_user = st.text_input("New Username", key="signup_user")
        signup_pass = st.text_input("New Password", type="password", key="signup_pass")
        if st.button("Signup"):
            success, msg = signup(signup_user, signup_pass)
            if success:
                st.session_state.user = signup_user
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

# --- Main app ---
else:
    st.title(f"📊 Daily Activity Tracker - {st.session_state.user}")

    # Sidebar filters
    st.sidebar.header("Filters")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM logs WHERE username=%s", (st.session_state.user,))
    categories = [row[0] for row in c.fetchall()]
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)
    c.close()
    conn.close()

    # Input keyword
    prompt = st.text_input("Enter a keyword (or 'keyword = category'):")

    if st.button("Submit") and prompt:
        result = log_entry(st.session_state.user, prompt)
        st.success(result)

    # Display logs
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

    # Keyword mapping
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)

    # Logout
    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()
