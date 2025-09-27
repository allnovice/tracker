# filename: tracker.py
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# --- Neon DB connection ---
def get_conn():
    return psycopg2.connect(st.secrets["NEON_CONN"])

# --- Initialize tables ---
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
    # Keyword mapping
    c.execute('''
        CREATE TABLE IF NOT EXISTS keyword_mapping (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    # Logs
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id),
            keyword TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Functions ---
def check_login(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=%s AND password=%s", (username, password))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def create_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id", (username, password))
        user_id = c.fetchone()[0]
        conn.commit()
        return user_id
    except:
        conn.rollback()
        return None
    finally:
        conn.close()

def log_entry(user_id, prompt):
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
        c.execute("INSERT INTO logs (user_id, keyword, category, timestamp) VALUES (%s, %s, %s, %s)", 
                  (user_id, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# --- Streamlit UI ---
st.set_page_config(page_title="📊 Daily Activity Tracker", layout="wide")
st.title("📊 Daily Activity Tracker")

# --- Session login ---
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None

login_tab, signup_tab = st.tabs(["Login", "Sign Up"])

with login_tab:
    st.subheader("Login")
    login_user = st.text_input("Username")
    login_pass = st.text_input("Password", type="password")
    if st.button("Login"):
        user_id = check_login(login_user, login_pass)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.username = login_user
            st.success(f"Logged in as {login_user}")
        else:
            st.error("Invalid username/password")

with signup_tab:
    st.subheader("Sign Up")
    new_user = st.text_input("New Username", key="new_user")
    new_pass = st.text_input("New Password", type="password", key="new_pass")
    if st.button("Create Account"):
        user_id = create_user(new_user, new_pass)
        if user_id:
            st.success(f"Account created. You can now login as {new_user}.")
        else:
            st.error("Username taken or error.")

# --- Only show app if logged in ---
if st.session_state.user_id:
    st.sidebar.header(f"Welcome, {st.session_state.username}!")
    # Sidebar filter
    conn = get_conn()
    categories = [row[0] for row in pd.read_sql("SELECT DISTINCT category FROM logs WHERE user_id=%s", conn, params=(st.session_state.user_id,)).values.tolist()]
    conn.close()
    selected_category = st.sidebar.selectbox("Filter by category:", ["All"] + categories)

    # Input
    prompt = st.text_input("Enter a keyword (or 'keyword = category'):")

    if st.button("Submit") and prompt:
        result = log_entry(st.session_state.user_id, prompt)
        st.success(result)

    # Display logs
    conn = get_conn()
    if selected_category == "All":
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE user_id=%s ORDER BY timestamp DESC LIMIT 50", conn, params=(st.session_state.user_id,))
    else:
        logs_df = pd.read_sql("SELECT keyword, category, timestamp FROM logs WHERE user_id=%s AND category=%s ORDER BY timestamp DESC LIMIT 50", conn, params=(st.session_state.user_id, selected_category))
    conn.close()

    if not logs_df.empty:
        st.subheader("📝 Recent Logs")
        st.dataframe(logs_df)
    else:
        st.info("No logs yet.")

    # Show keyword mapping
    conn = get_conn()
    mapping_df = pd.read_sql("SELECT keyword, category FROM keyword_mapping ORDER BY keyword", conn)
    conn.close()
    if not mapping_df.empty:
        st.subheader("📚 Keyword Mappings")
        st.dataframe(mapping_df)
