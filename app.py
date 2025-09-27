# app.py
from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2, os
from logs import logs_bp, log_entry  # import blueprint and helper

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.register_blueprint(logs_bp)

# Connect to Neon DB
def get_conn():
    db_url = os.environ.get("NEON")
    return psycopg2.connect(db_url)

# Initialize tables (users)
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

# Home
@app.route("/")
def home():
    if "user" in session:
        return f"<h1>Welcome, {session['user']}!</h1><a href='/logout'>Logout</a>"
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
            return redirect(url_for("home"))
        else:
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
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return render_template("signup.html", error="Username already exists")
        finally:
            conn.close()
        session["user"] = username
        return redirect(url_for("home"))
    return render_template("signup.html")

# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# Log route (must be before app.run)
@app.route("/log", methods=["GET", "POST"])
def log():
    if "user" not in session:
        return redirect("/login")
    
    message = ""
    if request.method == "POST":
        prompt = request.form.get("prompt")
        if prompt:
            message = log_entry(session["user"], prompt)
    
    return render_template("log.html", message=message)

if __name__ == "__main__":
    app.run(debug=True)
