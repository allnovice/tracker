from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Hello, Render!</h1><p>This is a minimal Flask app.</p>"

if __name__ == "__main__":
    app.run(debug=True)
