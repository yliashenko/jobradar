"""Token gate. The database holds a personal job-search history, so remote
access requires a token; with no token configured, only local connections pass.
"""

from flask import abort, current_app, request

_LOCAL = {"127.0.0.1", "::1", "localhost"}


def require_token(token_value: str) -> None:
    """Pass if authorised; abort(403) otherwise."""
    token = current_app.config.get("TOKEN", "")
    if not token:
        if request.remote_addr in _LOCAL:
            return
        abort(
            403,
            "webui.token in config.json is empty, so only local connections are "
            "accepted. Set a token and open /?token=…",
        )
    if token_value == token or request.headers.get("X-Jobradar-Token") == token:
        return
    abort(403, "Invalid or missing token.")
