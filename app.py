"""
Application factory for RxLogic.

Section 6.3: wires the rate limiter (extensions.py), the API
blueprint (routes/api.py), and the persistence layer (models/database.py)
together. Kept as a factory rather than a module-level app so tests
can build isolated instances.

Static serving: the built React app (frontend/dist, produced by
`npm run build`) is served directly by this Flask app so the whole
project ships as one Render service -- no separate frontend host, no
CORS configuration needed since everything is same-origin. If the
frontend hasn't been built yet (e.g. a fresh clone, or CI running the
Python test suite only), the root route degrades to a clear JSON
message instead of crashing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, send_from_directory

from extensions import limiter
from models.database import init_db
from routes.api import api

# -- configuration -------------------------------------------------------

load_dotenv()

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_PORT = 5000
DEFAULT_HOST = "0.0.0.0"

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

SERVICE_NAME = "RxLogic"
SERVICE_DESCRIPTION = "Hybrid LLM + symbolic reasoning core for medication scheduling."

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
    format=LOG_FORMAT,
)
logger = logging.getLogger(__name__)


# -- application factory --------------------------------------------------


def create_app() -> Flask:
    """Build and configure the Flask application.

    Route/extension setup order matters here: the `/api/info` route is
    registered onto the `api` blueprint *before* that blueprint is
    attached to the app. Flask freezes a blueprint's route table the
    moment `register_blueprint` runs, so registering first and adding
    routes after raises an `AssertionError` at import time.
    """
    app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="")
    app.config["JSON_SORT_KEYS"] = False

    init_db()
    limiter.init_app(app)

    _register_info_route(api)
    app.register_blueprint(api)

    _register_frontend_route(app)

    return app


def _register_info_route(blueprint: Any) -> None:
    """Attach the lightweight service-metadata endpoint to the API blueprint."""

    @blueprint.route("/info", methods=["GET"])
    def info() -> tuple[Response, int]:
        return (
            jsonify(
                {
                    "service": SERVICE_NAME,
                    "description": SERVICE_DESCRIPTION,
                    "api_health": "/api/health",
                }
            ),
            200,
        )


def _register_frontend_route(app: Flask) -> None:
    """Attach the catch-all route that serves the built React app.

    Real files (JS/CSS bundles, favicon, etc.) are served directly;
    anything else -- including client-side routes like /history --
    falls back to index.html so React Router can take over. Flask
    matches the more specific /api/... rules in routes/api.py before
    this catch-all, so it never shadows the API blueprint.
    """

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str) -> tuple[Response, int] | Response:
        static_root = Path(app.static_folder)

        if not static_root.is_dir():
            return (
                jsonify(
                    {
                        "error": "frontend_not_built",
                        "message": (
                            "The React app hasn't been built yet. Run "
                            "`npm install && npm run build` inside frontend/, "
                            "then restart."
                        ),
                    }
                ),
                503,
            )

        requested_file = static_root / path
        if path and requested_file.exists():
            return send_from_directory(static_root, path)
        return send_from_directory(static_root, "index.html")


app = create_app()

if __name__ == "__main__":  # pragma: no cover -- only runs via `python app.py`, never under pytest
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", DEFAULT_PORT))
    app.run(host=DEFAULT_HOST, port=port, debug=debug)