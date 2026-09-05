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

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory

from extensions import limiter
from models.database import init_db
from routes.api import api

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")
    app.config["JSON_SORT_KEYS"] = False

    init_db()

    limiter.init_app(app)
    app.register_blueprint(api)

    @api.route("/info", methods=["GET"])
    def info():
        return jsonify(
            {
                "service": "RxLogic",
                "description": "Hybrid LLM + symbolic reasoning core for medication scheduling.",
                "api_health": "/api/health",
            }
        ), 200

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        """
        Serves the built React app for every non-API route.

        Real files (JS/CSS bundles, favicon, etc.) are served directly;
        anything else -- including client-side routes like /history --
        falls back to index.html so React Router can take over. Flask
        matches the more specific /api/... rules in routes/api.py
        before this catch-all, so it never shadows the API blueprint.
        """
        if not os.path.isdir(app.static_folder):
            return jsonify(
                {
                    "error": "frontend_not_built",
                    "message": "The React app hasn't been built yet. Run "
                    "`npm install && npm run build` inside frontend/, then restart.",
                }
            ), 503

        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover -- only runs via `python app.py`, never under pytest
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=debug)