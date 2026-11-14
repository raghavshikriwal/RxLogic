"""Application factory for RxLogic with explicit web-tier hardening."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment before importing modules that read configuration at import.
load_dotenv()

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import safe_join

from extensions import limiter
from models.database import init_db
from routes.api import api
from routes.knowledge_api import knowledge_api
from routes.external_knowledge_api import external_knowledge_api
from services.security import build_security_settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_PORT = 5000
DEFAULT_HOST = "0.0.0.0"
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
SERVICE_NAME = "RxLogic"
SERVICE_DESCRIPTION = "Hybrid LLM + symbolic reasoning core for medication scheduling."

logging.basicConfig(level=os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Build a configured Flask app; production fails closed on weak secrets."""
    settings = build_security_settings(os.environ)
    app = Flask(__name__, static_folder=None)
    app.config.update(
        JSON_SORT_KEYS=False,
        DEBUG=bool(settings["debug"]),
        TESTING=False,
        MAX_CONTENT_LENGTH=int(settings["max_content_length"]),
        SESSION_COOKIE_SECURE=bool(settings["session_cookie_secure"]),
        SESSION_COOKIE_HTTPONLY=bool(settings["session_cookie_httponly"]),
        SESSION_COOKIE_SAMESITE=str(settings["session_cookie_samesite"]),
        SESSION_COOKIE_PATH=str(settings["session_cookie_path"]),
        RXLOGIC_ENV=str(settings["environment"]),
        RXLOGIC_SESSION_SIGNING_KEY=settings["session_signing_key"],
        RXLOGIC_TRUSTED_PROXY_HOPS=int(settings["trusted_proxy_hops"]),
        RXLOGIC_RATE_LIMIT_STORAGE_URI=str(settings["rate_limit_storage_uri"]),
        RATELIMIT_STORAGE_URI=str(settings["rate_limit_storage_uri"]),
        RXLOGIC_HSTS_ENABLED=bool(settings["hsts_enabled"]),
    )

    if app.config["RXLOGIC_TRUSTED_PROXY_HOPS"] > 0:
        # Trust only the explicitly configured number of reverse proxies.
        # Never enable this setting blindly: a wrong hop count allows clients
        # to influence the forwarded address used by rate limiting/logging.
        hops = app.config["RXLOGIC_TRUSTED_PROXY_HOPS"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops)

    if app.config["RXLOGIC_ENV"] == "production" and app.config["RXLOGIC_RATE_LIMIT_STORAGE_URI"].startswith("memory://"):
        logger.warning("Production is using process-local memory rate limiting; configure a shared Redis store.")

    init_db()
    limiter.init_app(app)
    app.register_blueprint(api)
    app.register_blueprint(knowledge_api)
    app.register_blueprint(external_knowledge_api)
    _register_frontend_route(app)
    _register_info_route(app)
    _register_security_hooks(app)
    _register_error_handlers(app)
    return app


def _register_info_route(app: Flask) -> None:
    @app.route("/api/info", methods=["GET"])
    def info() -> tuple[Response, int]:
        return jsonify({"service": SERVICE_NAME, "description": SERVICE_DESCRIPTION, "api_health": "/api/health"}), 200


def _register_frontend_route(app: Flask) -> None:
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str) -> tuple[Response, int] | Response:
        if path == "api" or path.startswith("api/"):
            return jsonify({"error": "http_404", "message": "API endpoint not found."}), 404
        static_root = FRONTEND_DIST
        if not static_root.is_dir():
            return jsonify({
                "error": "frontend_not_built",
                "message": "The React app has not been built. Run npm ci && npm run build inside frontend/.",
            }), 503
        requested_file = safe_join(str(static_root), path) if path else None
        if requested_file and Path(requested_file).is_file():
            return send_from_directory(static_root, path)
        return send_from_directory(static_root, "index.html")


def _register_security_hooks(app: Flask) -> None:
    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"

        if response.mimetype == "text/html":
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
                "form-action 'self'; script-src 'self'; img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; connect-src 'self'",
            )

        if app.config["RXLOGIC_HSTS_ENABLED"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")

        # Avoid disclosing the framework/server banner unnecessarily.
        response.headers.pop("Server", None)
        return response


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({
                "error": f"http_{error.code or 500}",
                "message": error.description,
            }), error.code or 500
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error: Exception):
        logger.exception("Unhandled application exception (%s)", type(error).__name__)
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "internal_server_error",
                "message": "An unexpected error occurred. Please try again later.",
            }), 500
        return jsonify({"error": "internal_server_error", "message": "An unexpected error occurred."}), 500


# WSGI entry point used by `gunicorn app:app`.
app = create_app()

if __name__ == "__main__":  # pragma: no cover
    port = int(os.getenv("PORT", DEFAULT_PORT))
    app.run(host=DEFAULT_HOST, port=port, debug=app.config["DEBUG"])
