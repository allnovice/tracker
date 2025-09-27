from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime
import psycopg2
import os

logs_bp = Blueprint('logs', __name__)

def get_conn():
    # Read Neon DB URL from environment variable
    neon_url = os.environ.get("NEON")  # make sure your secret is named 'NEON'
    if not neon_url:
        raise ValueError("NEON environment variable not set")
    return psycopg2.connect(neon_url)

@logs_bp.route("/log", methods=["GET", "POST"])
def log():
    if "user" not in session:
        return redirect("/login")
    message = ""
    if request.method == "POST":
        prompt = request.form.get("prompt")
        if "=" in prompt:
            keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        else:
            keyword = prompt.strip().lower()
            category = None  # could fetch from mapping table
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO logs (username, keyword, category, timestamp) VALUES (%s,%s,%s,%s)",
            (session["user"], keyword, category, datetime.now()),
        )
        conn.commit()
        conn.close()
        message = f"✅ Logged '{keyword}' under '{category}'"
    return render_template("log.html", message=message)
