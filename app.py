import logging

from flask import Flask, jsonify, redirect, request
from werkzeug.exceptions import NotFound

from knowledge import pipeline

logging.basicConfig(level=logging.INFO)

# In local dev Flask serves the UI from public/. On Vercel, public/** is
# served by the CDN and is NOT bundled into the function, so static_folder
# lookups fail there — routes must fall back to the CDN paths instead.
app = Flask(__name__, static_folder="public", static_url_path="")

MAX_QUESTION_LENGTH = 300


@app.route("/")
def index():
    try:
        return app.send_static_file("index.html")
    except NotFound:
        return redirect("/index.html", code=307)


@app.route("/api/ask")
def ask():
    question = (request.args.get("q") or "").strip()
    if not question:
        return jsonify({"error": "Missing question. Use /api/ask?q=..."}), 400
    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({"error": f"Question too long (max {MAX_QUESTION_LENGTH} chars)."}), 400
    try:
        return jsonify(pipeline.answer(question))
    except Exception:
        app.logger.exception("pipeline failure for question: %s", question)
        return jsonify({"error": "Something went wrong while researching that."}), 500


if __name__ == "__main__":
    import os

    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
