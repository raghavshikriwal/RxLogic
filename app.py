"""
Application factory for RxLogic.

Section 6.3: wires the rate limiter (extensions.py), the API
blueprint (routes/api.py), and the persistence layer (models/database.py)
together. Kept as a factory rather than a module-level app so tests
can build isolated instances.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify

from extensions import limiter
from models.database import init_db
from routes.api import api

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    init_db()

    limiter.init_app(app)
    app.register_blueprint(api)

    @app.route("/")
    def index():
        return jsonify(
            {
                "service": "RxLogic",
                "description": "Hybrid LLM + symbolic reasoning core for medication scheduling.",
                "api_health": "/api/health",
            }
        ), 200

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover -- only runs via `python app.py`, never under pytest
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=debug)