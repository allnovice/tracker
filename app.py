# filename: app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- DB Connection ---
def get_conn():
    return psycopg2.connect(st.secrets["NEON_CONN"])

# --- DB Init ---
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
    # Keyword mapping table
    c.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    """)
    # Logs table
    c.execute("""
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

init_db()

# --- Auth Functions ---
def signup_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        conn.close()
        return True, f"Signup successful! Welcome {username}"
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        conn.close()
        return False, "Username already exists."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)

def login_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    row = c.fetchone()
    conn.close()
    if row:
        return True, f"Logged in as {username}"
    else:
        return False, "Invalid username or password."

# --- Logging Functions ---
def log_entry(username, prompt):
    conn = get_conn()
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("""
            INSERT INTO keyword_mapping (username, keyword, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (keyword) DO UPDATE SET category=EXCLUDED.category
        """, (username, keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE username=%s AND keyword=%s", (username, keyword))
        row = c.fetchone()
        if row:
            category = row[0]
        else:
            category = None

    if category:
        c.execute("INSERT INTO logs (username, keyword, category) VALUES (%s, %s, %s)",
                  (username, keyword, category))
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

st.title("📊 Daily Activity Tracker")

# --- Logged in header & logout ---
if st.session_state.user:
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown(f"**Logged in as:** {st.session_state.user}")
    with col2:
        if st.button("Logout"):
            st.session_state.user = None
            st.experimental_rerun()

# --- Authentication ---
if not st.session_state.user:
    tab1, tab2 = st.tabs(["Login", "Signup"])
    with tab1:
        login_user_input = st.text_input("Username", key="login_user")
        login_pass_input = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            success, msg = login_user(login_user_input, login_pass_input)
            if success:
                st.session_state.user = login_user_input
                st.success(msg)
                st.experimental_rerun()
            else:
                st.error(msg)
    with tab2:
        signup_user_input = st.text_input("Username", key="signup_user")
        signup_pass_input = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Signup"):
            success, msg = signup_user(signup_user_input, signup_pass_input)
            if success:
                st.session_state.user = signup_user_input
                st.success(msg)
                st.experimental_rerun()
            else:
                st.error(msg)
else:
    # --- Main App: Sidebar & Logs ---
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
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s ORDER BY timestamp DESC LIMIT 50",
                              conn, params=(st.session_state.user,))
    else:
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=%s AND category=%s ORDER BY timestamp DESC LIMIT 50",
                              conn, params=(st.session_state.user, selected_category))
    conn.close()

    if not logs_df.empty:
        st.subheader("📝 Recent Logs")
        st.dataframe(logs_df)
    else:
        st.info("No logs yet.")

    # Optional: show keyword mapping
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping WHERE username=%s ORDER BY keyword",
                             conn, params=(st.session_state.user,))
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
