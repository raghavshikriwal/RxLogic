"""
Application factory for RxLogic.

Section 6.3: wires the rate limiter (extensions.py) and the API
blueprint (routes/api.py) together. Kept as a factory rather than a
module-level app so tests can build isolated instances.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, jsonify

from extensions import limiter
from routes.api import api

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

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

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=debug)