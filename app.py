# app.py
from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2, os
from logs import log_entry
from psycopg2.errors import UniqueViolation

app = Flask(__name__)
app.secret_key = "supersecretkey"  # sessions

# Connect to Neon DB
def get_conn():
    db_url = os.environ.get("NEON")
    return psycopg2.connect(db_url)

# Initialize users table
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Home redirects to logs if logged in
@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("log"))
    return redirect(url_for("login"))

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        conn.close()
        if user:
            session["user"] = username
            return redirect(url_for("log"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
        except UniqueViolation:
            conn.rollback()
            return render_template("signup.html", error="Username already exists")
        finally:
            conn.close()
        session["user"] = username
        return redirect(url_for("log"))
    return render_template("signup.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))
    
# Log route
@app.route("/log", methods=["GET", "POST"])
def log():
    if "user" not in session:
        return redirect(url_for("login"))

    message = ""
    logs = []

    conn = get_conn()
    cur = conn.cursor()

    # Handle form submission
    if request.method == "POST":
        prompt = request.form.get("prompt")
        if prompt:
            message = log_entry(session["user"], prompt)

    # Fetch last 10 logs for this user
    cur.execute("""
        SELECT keyword, category, timestamp
        FROM logs
        WHERE username = %s
        ORDER BY timestamp DESC
        LIMIT 10
    """, (session["user"],))
    logs = cur.fetchall()  # list of tuples
    conn.close()

    # Convert to list of dicts for template
    logs_dict = [{"keyword": row[0], "category": row[1], "timestamp": row[2]} for row in logs]

    return render_template("log.html", message=message, logs=logs_dict)
