# filename: app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- Streamlit Page Config ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")

# --- Neon DB Connection ---
def get_conn():
    conn_str = st.secrets["NEON_CONN"]
    return psycopg2.connect(conn_str)

# --- Initialize DB ---
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
    # Keyword mapping table
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    # Logs table (add username column if missing)
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Functions ---
def signup(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        return True, "Signup successful!"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False, "Username already exists."
    finally:
        conn.close()

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
        c.execute("INSERT INTO keyword_mapping (keyword, category) VALUES (%s, %s) ON CONFLICT (keyword) DO UPDATE SET category=EXCLUDED.category", (keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE keyword=%s", (keyword,))
        row = c.fetchone()
        category = row[0] if row else None

    if category:
        c.execute("INSERT INTO logs (username, keyword, category, timestamp) VALUES (%s, %s, %s, %s)",
                  (username, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Persistent Login via query params ---
params = st.experimental_get_query_params()
if "user" in params:
    st.session_state.user = params["user"][0]

# --- Login / Signup ---
if "user" not in st.session_state:
    st.title("🔐 Login / Signup")
    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login(login_user, login_pass):
                st.session_state.user = login_user
                st.experimental_set_query_params(user=login_user)
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        signup_user = st.text_input("Username", key="signup_user")
        signup_pass = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Signup"):
            success, msg = signup(signup_user, signup_pass)
            if success:
                # Auto login after signup
                st.session_state.user = signup_user
                st.experimental_set_query_params(user=signup_user)
                st.experimental_rerun()
            else:
                st.error(msg)
else:
    # --- Main App ---
    st.title(f"📊 Daily Activity Tracker - {st.session_state.user}")

    # Logout button
    col1, col2 = st.columns([0.9, 0.1])
    with col2:
        if st.button("Logout"):
            del st.session_state.user
            st.experimental_set_query_params()
            st.experimental_rerun()

    # Sidebar filter
    st.sidebar.header("Filters")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM logs WHERE username=%s", (st.session_state.user,))
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

    # Input
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

    # Optional: show category mapping
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
