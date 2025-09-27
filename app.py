from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Hello, Render!</h1><p>This is a minimal Flask app.</p>"
