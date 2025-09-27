# filename: app.py
import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime

# --- DB connection ---
def get_conn():
    conn_str = st.secrets["NEON_CONN"]
    return psycopg2.connect(conn_str)

# --- Initialize tables ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    """)
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

# --- Auth functions ---
def signup(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        conn.commit()
        st.session_state.user = username
        st.success("✅ Signed up and logged in!")
    except psycopg2.errors.UniqueViolation:
        st.error("⚠️ Username already exists.")
    finally:
        conn.close()

def login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        st.session_state.user = username
        st.success("✅ Logged in!")
    else:
        st.error("❌ Invalid username or password.")

# --- Log entry ---
def log_entry(prompt):
    username = st.session_state.user
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
        category = row[0] if row else None

    if category:
        c.execute("INSERT INTO logs (username, keyword, category, timestamp) VALUES (%s,%s,%s,%s)",
                  (username, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit UI ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None

# --- Login / Signup ---
if not st.session_state.user:
    st.title("🔐 Login / Signup")
    tab = st.radio("Choose:", ["Login", "Signup"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Submit"):
        if tab == "Login":
            login(username, password)
        else:
            signup(username, password)

# --- Main App ---
if st.session_state.user:
    st.title(f"📊 Daily Tracker — User: {st.session_state.user}")

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
        result = log_entry(prompt)
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

    # Keyword mapping
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping WHERE username=%s ORDER BY keyword",
                             conn, params=(st.session_state.user,))
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)

    # Logout button
    if st.button("Logout"):
        st.session_state.user = None
        st.experimental_rerun()
