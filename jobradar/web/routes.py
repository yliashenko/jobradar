"""HTTP routes for the web UI.

Thin handlers: authorise, open the DB, gather a context dict via web.views, and
render a Jinja template. GET pages, POST actions (run trigger, status change,
profile save/preview), and the static/resource whitelist.
"""

import json
import os
import urllib.parse

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
)

from jobradar import candidate as profile_data
from jobradar import paths
from jobradar.core.cover import DEFAULT_MODEL as COVER_MODEL
from jobradar.core.cover import generate_cover, load_facts
from jobradar.core.db import now_iso
from jobradar.core.notify import effective_threshold
from jobradar.core.scoring import llm_settings
from jobradar.web import views
from jobradar.web.auth import require_token
from jobradar.web.constants import STATUS_LABELS
from jobradar.web.db import get_db
from jobradar.web.format import render_markdown
from jobradar.web.forms import (
    parse_hiring_update,
    parse_profile_preview,
    parse_profile_save,
    parse_settings_save,
)

bp = Blueprint("web", __name__)

# Source logos on cards. A basename whitelist keeps /resources from turning into
# arbitrary file reads. No auth: these are public logos, not database data.
_RESOURCES = {"dou_logo.png": "image/png", "djinni_logo.png": "image/png"}


def _params() -> dict:
    """Flatten the query string into the params dict the views expect: repeated
    keys joined — company names may contain commas, so `co` joins on newline."""
    return {
        k: ("\n" if k == "co" else ",").join(request.args.getlist(k))
        for k in request.args
    }


def _run_status() -> dict:
    runner = current_app.config.get("RUNNER")
    return runner.status() if runner is not None else {}


def _query() -> str:
    return request.query_string.decode("utf-8")


def _redirect_back(back: str):
    return redirect("/?" + back if back else "/", code=303)


def _empty():
    """Pre-first-scan page (no database yet)."""
    return render_template("empty.html", **views.empty_context(_run_status(), _query()))


@bp.route("/health")
def health():
    return "<p>ok</p>"


@bp.route("/resources/<path:name>")
def resources(name):
    base = os.path.basename(name)
    ctype = _RESOURCES.get(base)
    path = os.path.join(paths.resources_dir(), base)
    if ctype is None or not os.path.exists(path):
        abort(404)
    resp = send_file(path, mimetype=ctype)
    resp.headers["Cache-Control"] = "max-age=300"
    return resp


@bp.route("/")
def feed():
    params = _params()
    require_token(params.get("token", ""))
    conn = get_db()
    if conn is None:
        return _empty()
    return render_template(
        "feed.html",
        title="feed",
        active="feed",
        params=params,
        **views.feed_context(
            conn, params, effective_threshold(), _run_status(), _query()
        ),
    )


@bp.route("/company")
def company():
    params = _params()
    require_token(params.get("token", ""))
    conn = get_db()
    if conn is None:
        return _empty()
    return render_template(
        "company.html",
        title=params.get("name") or "company",
        active="",
        params=params,
        query=_query(),
        **views.company_context(conn, params, effective_threshold()),
    )


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "POST":
        return _handle_profile()
    params = _params()
    require_token(params.get("token", ""))
    return _render_profile(
        params, profile_data.load(), saved=(params.get("saved") == "1")
    )


def _render_profile(params, data, preview=None, saved=False):
    """VIEW or EDIT — standard CRUD states. An empty profile has nothing to save
    from, so it opens in EDIT; ?edit=1 forces EDIT; otherwise VIEW."""
    editing = (
        preview is not None
        or params.get("edit") == "1"
        or not os.path.exists(paths.profile_json_path())
    )
    kwargs = {"title": "profile", "active": "profile", "params": params}
    if editing:
        return render_template(
            "profile_edit.html",
            **kwargs,
            **views.profile_edit_context(params, data, preview),
        )
    return render_template(
        "profile_view.html",
        **kwargs,
        **views.profile_view_context(params, data, saved),
    )


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        return _handle_settings()
    params = _params()
    require_token(params.get("token", ""))
    return _render_settings(
        params, profile_data.load(), saved=(params.get("saved") == "1")
    )


def _render_settings(params, data, saved=False):
    """LLM access, Telegram and auto-scan. Same VIEW/EDIT states as the profile:
    no settings file yet → EDIT; ?edit=1 forces EDIT; otherwise VIEW. The context
    is a superset of what these templates read (shared with the profile page)."""
    editing = params.get("edit") == "1" or not os.path.exists(paths.profile_json_path())
    kwargs = {"title": "settings", "active": "settings", "params": params}
    if editing:
        return render_template(
            "settings_edit.html", **kwargs, **views.profile_edit_context(params, data)
        )
    return render_template(
        "settings_view.html",
        **kwargs,
        **views.profile_view_context(params, data, saved),
    )


@bp.route("/tags")
def tags():
    params = _params()
    require_token(params.get("token", ""))
    conn = get_db()
    if conn is None:
        return _empty()
    return render_template(
        "tags.html",
        title="market stack",
        active="tags",
        params=params,
        **views.tags_context(conn, params),
    )


@bp.route("/runs")
def runs():
    params = _params()
    require_token(params.get("token", ""))
    conn = get_db()
    if conn is None:
        return _empty()
    return render_template(
        "runs.html",
        title="how this was counted",
        active="runs",
        params=params,
        **views.runs_context(conn, params),
    )


@bp.route("/stats")
def stats():
    params = _params()
    require_token(params.get("token", ""))
    conn = get_db()
    if conn is None:
        return _empty()
    return render_template(
        "stats.html",
        title="stats",
        active="stats",
        params=params,
        **views.stats_context(conn, params),
    )


@bp.route("/calendar")
def calendar():
    params = _params()
    require_token(params.get("token", ""))
    conn = get_db()
    if conn is None:
        return _empty()
    return render_template(
        "calendar.html",
        title="calendar",
        active="calendar",
        params=params,
        **views.calendar_context(conn, params),
    )


@bp.route("/run", methods=["POST"])
def run():
    back = request.form.get("back", "")
    require_token(dict(urllib.parse.parse_qsl(back)).get("token", ""))
    runner = current_app.config.get("RUNNER")
    if runner is None:
        abort(503, "The collector isn't connected to this server.")
    # A repeated press during a run doesn't spawn a second process: trigger()
    # returns 'busy' and we just send the person back to the same page.
    runner.trigger()
    return _redirect_back(back)


@bp.route("/status", methods=["POST"])
def status():
    back = request.form.get("back", "")
    require_token(dict(urllib.parse.parse_qsl(back)).get("token", ""))
    digest = request.form.get("hash", "")
    new_status = request.form.get("status", "")
    if new_status not in STATUS_LABELS or not digest:
        abort(400, "Unknown status or empty identifier.")
    conn = get_db()
    if conn is None:
        abort(404, "No database yet.")
    conn.execute(
        "UPDATE jobs SET status = ?, status_at = ? WHERE hash = ?",
        (new_status, now_iso(), digest),
    )
    conn.commit()
    return _redirect_back(back)


@bp.route("/hiring/update", methods=["POST"])
def hiring_update():
    back = request.form.get("back", "")
    require_token(dict(urllib.parse.parse_qsl(back)).get("token", ""))
    upd = parse_hiring_update()
    if upd is None:
        abort(400, "Bad hiring update.")
    conn = get_db()
    if conn is None:
        abort(404, "No database yet.")
    row = conn.execute(
        "SELECT hiring_status, hiring_notes FROM jobs WHERE hash = ?", (upd["hash"],)
    ).fetchone()
    if row is None:
        abort(404, "No such vacancy.")
    notes = {}
    if row["hiring_notes"]:
        try:
            loaded = json.loads(row["hiring_notes"])
            notes = loaded if isinstance(loaded, dict) else {}
        except (ValueError, TypeError):
            notes = {}
    # Save the note the textarea was showing (its stage), then optionally move to
    # the stage the pressed button asks for — so switching never drops an edit.
    if upd["stage"]:
        notes[upd["stage"]] = upd["note"]
    new_stage = upd["go"] or row["hiring_status"]
    # Archive/restore also flip the job's triage status. We never touch status_at:
    # the applied date must stay put so the activity calendar keeps the record.
    status_set = ""
    if upd["archive"]:
        new_stage = "finish"  # archiving is only offered from the finish stage
        status_set = ", status = 'archived'"
    elif upd["restore"]:
        status_set = ", status = 'applied'"
    conn.execute(
        f"UPDATE jobs SET hiring_status = ?, hiring_notes = ?{status_set} WHERE hash = ?",
        (new_stage, json.dumps(notes, ensure_ascii=False), upd["hash"]),
    )
    conn.commit()
    # The pipeline now lives on the feed's Applied tab; `back` carries its query
    # (status=applied[&archived=1]…), so return the person to the same view.
    return _redirect_back(back)


@bp.route("/hiring/cover", methods=["POST"])
def hiring_cover():
    """Generate (or return the saved) cover letter for an applied vacancy.

    Returns JSON so the card's ✍ button can show a spinner and fill the modal
    without a page reload. Configuration/data problems come back as
    {ok: false, error} with a 200, so the popup shows the reason as text — the
    "if the skill isn't set up, show a popup" case is a missing career-facts.md
    or API key.
    """
    require_token(request.form.get("token", ""))
    conn = get_db()
    if conn is None:
        return jsonify(ok=False, error="No database yet."), 404
    digest = request.form.get("hash", "")
    regenerate = request.form.get("regenerate", "") == "1"
    row = conn.execute(
        "SELECT title, company, location, salary, description, cover_data "
        "FROM jobs WHERE hash = ?",
        (digest,),
    ).fetchone()
    if row is None:
        return jsonify(ok=False, error="No such vacancy."), 404
    if row["cover_data"] and not regenerate:
        try:
            return _cover_json(json.loads(row["cover_data"]), cached=True)
        except (ValueError, TypeError):
            pass  # malformed cache → fall through and regenerate

    facts = load_facts()
    if not facts:
        return jsonify(
            ok=False,
            error="career-facts.md is not in the jobradar data directory. "
            "Add it next to config.json to generate cover letters.",
        )
    cfg = current_app.config.get("JOBRADAR", {}) or {}
    cl = cfg.get("cover_letter", {}) or {}
    # Provider/key precedence shared with the scorer (Profile → config → env), so a
    # handed-off tool runs every LLM feature on the new owner's account/provider.
    provider, base_url, api_key = llm_settings(cfg)
    if not api_key:
        return jsonify(
            ok=False,
            error="No API key. Add your API key in Settings → LLM access "
            "(or set scorer.api_key / ANTHROPIC_API_KEY).",
        )
    # The cover-letter model is the profile's llm_model (scoring keeps its own).
    model = profile_data.load().get("llm_model") or cl.get("model", COVER_MODEL)
    timeout = int(cl.get("timeout_seconds", 120))
    try:
        result = generate_cover(
            row, facts, api_key, model, timeout, provider=provider, base_url=base_url
        )
    except Exception as exc:
        # Any failure (network, bad JSON, timeout) becomes popup text, not a 500.
        return jsonify(ok=False, error=f"Generation failed: {exc}")

    result["model"] = model
    result["generated_at"] = now_iso()
    conn.execute(
        "UPDATE jobs SET cover_data = ? WHERE hash = ?",
        (json.dumps(result, ensure_ascii=False), digest),
    )
    conn.commit()
    return _cover_json(result, cached=False)


def _cover_json(data, cached):
    """The cover-letter JSON the ✍ modal fills, with the eval/traceability
    markdown pre-rendered to HTML so the client and the server render identically."""
    return jsonify(
        ok=True,
        cached=cached,
        evaluation_html=render_markdown(data.get("evaluation", "")),
        traceability_html=render_markdown(data.get("traceability", "")),
        **data,
    )


def _handle_profile():
    token = request.form.get("token", "")
    require_token(token)
    action = request.form.get("action", "save")
    params = {"token": token} if token else {}

    if action == "preview":
        data, parsed = parse_profile_preview()
        return _render_profile(params, data, preview=parsed)

    _save_partial(parse_profile_save())
    return _after_save(action, token, "/profile")


def _handle_settings():
    token = request.form.get("token", "")
    require_token(token)
    action = request.form.get("action", "save")
    _save_partial(parse_settings_save())
    return _after_save(action, token, "/settings")


def _save_partial(fields: dict) -> None:
    """Merge a page's fields into the stored profile and save. The Profile and
    Settings pages each own half of profile.json; merging over what's on disk lets
    either page save without wiping the other's fields."""
    data = profile_data.load()
    data.update(fields)
    profile_data.save(data)


def _after_save(action, token, page):
    """Redirect after a save: 'save_scan' kicks a scan and lands on the feed;
    a plain save returns to the page with the saved flag."""
    runner = current_app.config.get("RUNNER")
    if action == "save_scan" and runner is not None:
        runner.trigger()
        suffix = "token=" + urllib.parse.quote(token) if token else ""
        return redirect("/?" + suffix, code=303)
    suffix = "&token=" + urllib.parse.quote(token) if token else ""
    return redirect(f"{page}?saved=1" + suffix, code=303)
