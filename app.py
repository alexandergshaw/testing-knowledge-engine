import logging

from flask import Flask, jsonify, redirect, request
from werkzeug.exceptions import NotFound

from knowledge import schedule

logging.basicConfig(level=logging.INFO)

# In local dev Flask serves the UI from public/. On Vercel, public/** is
# served by the CDN and is NOT bundled into the function, so static_folder
# lookups fail there — routes must fall back to the CDN paths instead.
app = Flask(__name__, static_folder="public", static_url_path="")

MAX_DESCRIPTION_LENGTH = 5000
MIN_DESCRIPTION_LENGTH = 15


@app.route("/")
def index():
    try:
        return app.send_static_file("index.html")
    except NotFound:
        return redirect("/index.html", code=307)


@app.route("/api/schedule", methods=["POST"])
def make_schedule():
    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()
    weeks = data.get("weeks")

    if len(description) < MIN_DESCRIPTION_LENGTH:
        return jsonify({"error": "Please provide a course description."}), 400
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return jsonify(
            {"error": f"Description too long (max {MAX_DESCRIPTION_LENGTH} chars)."}
        ), 400
    try:
        weeks = int(weeks)
    except (TypeError, ValueError):
        return jsonify({"error": "Number of weeks must be a whole number."}), 400
    if not schedule.MIN_WEEKS <= weeks <= schedule.MAX_WEEKS:
        return jsonify(
            {"error": f"Weeks must be between {schedule.MIN_WEEKS} and {schedule.MAX_WEEKS}."}
        ), 400

    try:
        result = schedule.build_schedule(description, weeks)
    except Exception:
        app.logger.exception("schedule failure")
        return jsonify({"error": "Something went wrong while building the schedule."}), 500
    if "error" in result:
        return jsonify(result), 422
    return jsonify(result)


if __name__ == "__main__":
    import os

    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
