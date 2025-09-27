# filename: tracker.py
import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

DB_FILE = "logs.db"

# --- Initialize DB ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    # Logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- User login ---
def login(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    result = c.fetchone()
    conn.close()
    return result is not None

def signup(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# --- Log entry ---
def log_entry(username, prompt):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("INSERT OR REPLACE INTO keyword_mapping (username, keyword, category) VALUES (?, ?, ?)",
                  (username, keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE username=? AND keyword=?", (username, keyword))
        row = c.fetchone()
        if row:
            category = row[0]
        else:
            category = None

    if category:
        c.execute("INSERT INTO logs (username, keyword, category, timestamp) VALUES (?, ?, ?, ?)",
                  (username, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit App ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")
st.title("📊 Daily Activity Tracker")

# Session state for login
if "user" not in st.session_state:
    st.session_state.user = None

# --- Sidebar: Login / Signup ---
with st.sidebar:
    if st.session_state.user is None:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.button("Login")
        signup_btn = st.button("Sign Up")

        if login_btn and username and password:
            if login(username, password):
                st.session_state.user = username
                st.success(f"Logged in as {username}")
            else:
                st.error("Invalid username or password")

        if signup_btn and username and password:
            if signup(username, password):
                st.success("Account created! You can now log in.")
            else:
                st.error("Username already exists")
    else:
        st.info(f"Logged in as {st.session_state.user}")
        if st.button("Logout"):
            st.session_state.user = None

# --- Main app: only if logged in ---
if st.session_state.user:
    current_user = st.session_state.user

    # Input
    prompt = st.text_input("Enter a keyword (or 'keyword = category'):")
    if st.button("Submit") and prompt:
        result = log_entry(current_user, prompt)
        st.success(result)

    # Sidebar filter
    st.sidebar.subheader("Filters")
    conn = sqlite3.connect(DB_FILE)
    categories = [row[0] for row in conn.execute("SELECT DISTINCT category FROM logs WHERE username=?", (current_user,)).fetchall()]
    conn.close()
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

    # Display logs
    conn = sqlite3.connect(DB_FILE)
    if selected_category == "All":
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=? ORDER BY timestamp DESC LIMIT 50",
                              conn, params=(current_user,))
    else:
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE username=? AND category=? ORDER BY timestamp DESC LIMIT 50",
                              conn, params=(current_user, selected_category))
    conn.close()

    if not logs_df.empty:
        st.subheader("📝 Recent Logs")
        st.dataframe(logs_df)
    else:
        st.info("No logs yet.")

    # Optional: show category mapping
    conn = sqlite3.connect(DB_FILE)
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping WHERE username=? ORDER BY keyword", conn, params=(current_user,))
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
