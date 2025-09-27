# logs.py
from flask import Blueprint, render_template, request, session
import psycopg2, os
from datetime import datetime

logs_bp = Blueprint("logs", __name__, template_folder="templates")

def get_conn():
    db_url = os.environ.get("NEON")
    return psycopg2.connect(db_url)

# Helper function for logging
def log_entry(user, prompt):
    conn = get_conn()
    c = conn.cursor()

    if "=" in prompt:
        keyword, category = [x.strip().lower() for x in prompt.split("=", 1)]
        c.execute("""
            INSERT INTO keyword_mapping (username, keyword, category)
            VALUES (%s, %s, %s)
            ON CONFLICT (username, keyword) DO UPDATE
            SET category=EXCLUDED.category
        """, (user, keyword, category))
    else:
        keyword = prompt.strip().lower()
        c.execute("SELECT category FROM keyword_mapping WHERE username=%s AND keyword=%s", (user, keyword))
        row = c.fetchone()
        category = row[0] if row else None

    if category:
        c.execute("""
            INSERT INTO logs (username, keyword, category, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (user, keyword, category, datetime.now()))
        conn.commit()
        conn.close()
        return f"✅ Logged '{keyword}' under '{category}'"
    else:
        conn.close()
        return f"⚠️ Category unknown for '{keyword}'. Define it using 'keyword = category'."

# Flask route
@logs_bp.route("/log", methods=["GET", "POST"])
def log_route():
    if "user" not in session:
        return redirect("/login")
    
    message = ""
    if request.method == "POST":
        prompt = request.form.get("prompt")
        if prompt:
            message = log_entry(session["user"], prompt)
    
    return render_template("log.html", message=message)
