"""Flask application factory for the jobradar web UI.

`create_app()` wires config, auth, the per-request DB, security headers, and the
routes blueprint. `main()` is the `python -m jobradar serve` entry point: it
loads config, builds the scan Runner, and runs the dev server.
"""

from __future__ import annotations

import argparse
import json
import os

from flask import Flask

from jobradar import paths
from jobradar.config import setup_logging
from jobradar.runner import Runner
from jobradar.web.db import close_db
from jobradar.web.filters import register_jinja
from jobradar.web.routes import bp


def load_config() -> dict:
    if not os.path.exists(paths.config_path()):
        return {}
    with open(paths.config_path(), encoding="utf-8") as fh:
        return json.load(fh)


def create_app(config: dict | None = None, runner=None) -> Flask:
    app = Flask(
        __name__,
        static_folder=paths.static_dir(),
        static_url_path="/static",
        template_folder=str(paths.PACKAGE_DIR / "templates"),
    )
    cfg = config if config is not None else load_config()
    app.config["JOBRADAR"] = cfg
    app.config["THRESHOLD"] = float(cfg.get("notify_min_score", 7))
    app.config["TOKEN"] = (cfg.get("webui", {}) or {}).get("token", "")
    app.config["RUNNER"] = runner

    app.register_blueprint(bp)
    register_jinja(app)
    app.teardown_appcontext(close_db)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if resp.mimetype == "text/html":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


def main() -> int:
    cfg = load_config()
    webui = cfg.get("webui", {}) or {}

    parser = argparse.ArgumentParser(description="jobradar web UI")
    parser.add_argument("--host", default=webui.get("host", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(webui.get("port", 8787)))
    args = parser.parse_args()

    # A button-triggered scan must leave the same trace in the log as a
    # scheduled one — when something breaks, there's one file to read.
    setup_logging(verbose=False)
    app = create_app(cfg, runner=Runner(cfg))

    token = webui.get("token", "")
    suffix = f"?token={token}" if token else ""
    print(f"jobradar web: http://{args.host}:{args.port}/{suffix}")
    if not token:
        print("webui.token is empty — accepting local connections only.")
    app.run(host=args.host, port=args.port, threaded=True)
    return 0
