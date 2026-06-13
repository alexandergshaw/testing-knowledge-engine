import logging

from flask import Flask, redirect, request
from werkzeug.exceptions import NotFound

from service import MAX_UPLOAD_BYTES, allowed_origin, api, error_response

logging.basicConfig(level=logging.INFO)

# In local dev Flask serves the UI from public/. On Vercel, public/** is
# served by the CDN and is NOT bundled into the function, so static_folder
# lookups fail there — routes must fall back to the CDN paths instead.
app = Flask(__name__, static_folder="public", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1024 * 1024
app.register_blueprint(api)


@app.route("/")
def index():
    try:
        return app.send_static_file("index.html")
    except NotFound:
        return redirect("/index.html", code=307)


@app.after_request
def add_cors_headers(response):
    """API consumers may call from other origins; the bundled UI is same-origin
    so this is harmless for it. Key travels in a header (not a cookie), so a
    wildcard origin is safe."""
    response.headers["Access-Control-Allow-Origin"] = allowed_origin(
        request.headers.get("Origin", "")
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, X-API-Key, Authorization"
    )
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Vary"] = "Origin"
    return response


# An API should answer with JSON even for framework-level errors, not Flask's
# default HTML pages.
@app.errorhandler(404)
def handle_404(error):
    return error_response("not_found", "Resource not found.", 404)


@app.errorhandler(405)
def handle_405(error):
    return error_response("method_not_allowed", "Method not allowed for this endpoint.", 405)


@app.errorhandler(413)
def handle_413(error):
    return error_response(
        "payload_too_large",
        f"Upload too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        413,
    )


@app.errorhandler(500)
def handle_500(error):
    return error_response("internal_error", "Something went wrong.", 500)


if __name__ == "__main__":
    import os

    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
