# app.py
from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import os
from logs import logs_bp


app.register_blueprint(logs_bp)
app = Flask(__name__)
app.secret_key = "supersecretkey"  # required for sessions

# Connect to Neon DB
def get_conn():
    db_url = os.environ.get("NEON")
    return psycopg2.connect(db_url)

# Home page
@app.route("/")
def home():
    if "user" in session:
        return f"<h1>Welcome, {session['user']}!</h1><a href='/logout'>Logout</a>"
    return redirect(url_for("login"))

# Login page
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

# Signup page
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_conn()
        cur = conn.cursor()
        # create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
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

if __name__ == "__main__":
    app.run(debug=True)
