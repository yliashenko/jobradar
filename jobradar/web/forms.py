"""Parse POST form data into the shapes the domain expects."""

import re

from flask import request

from jobradar import candidate as profile_data
from jobradar import roles, skills
from jobradar.web.constants import HIRING_LABELS


def _split(value: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,\n]", value or "") if t.strip()]


def _int(value, default: int) -> int:
    """A whole-number form field with a fallback — blank/garbage keeps the default."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _llm_endpoint() -> dict:
    """Map the 3-way provider dropdown to the stored pair. Only 'custom' keeps a
    base URL; Anthropic and plain OpenAI use their default endpoint, so any URL left
    in the (hidden) field is dropped — no stale endpoint survives a provider switch."""
    prov = request.form.get("llm_provider", "").strip()
    base = request.form.get("llm_base_url", "").strip()
    if prov == "custom":
        return {"llm_provider": "openai", "llm_base_url": base}
    if prov not in ("anthropic", "openai"):
        prov = "anthropic"
    return {"llm_provider": prov, "llm_base_url": ""}


def _telegram_and_schedule() -> dict:
    """The bot switch, notify threshold and auto-scan schedule — shared verbatim by
    save and preview so a CV re-detect doesn't wipe them."""
    return {
        "telegram_bot_token": request.form.get("telegram_bot_token", "").strip(),
        "telegram_chat_id": request.form.get("telegram_chat_id", "").strip(),
        "telegram_enabled": request.form.get("telegram_enabled") == "on",
        "notify_min_score": request.form.get("notify_min_score", "").strip(),
        "heartbeat_alert_hours": _int(request.form.get("heartbeat_alert_hours"), 24),
        "schedule_enabled": request.form.get("schedule_enabled") == "on",
        "schedule_interval_hours": _int(request.form.get("schedule_interval_hours"), 3),
        "schedule_start_hour": _int(request.form.get("schedule_start_hour"), 8),
        "schedule_end_hour": _int(request.form.get("schedule_end_hour"), 23),
    }


def parse_hiring_update() -> dict | None:
    """A hiring-card POST: `stage` is the stage the textarea edits, `note` its
    text, `go` the stage a pressed button moves to (empty on a plain Save). The
    route merges these into the per-stage notes JSON. `archive` finalizes the
    pipeline (job status → archived); `restore` brings an archived one back to
    applied. Unknown stage → None."""
    digest = request.form.get("hash", "")
    if not digest:
        return None
    stage = request.form.get("stage", "")
    go = request.form.get("go", "")
    if stage and stage not in HIRING_LABELS:
        return None
    if go and go not in HIRING_LABELS:
        return None
    return {
        "hash": digest,
        "stage": stage,
        "note": request.form.get("note", ""),
        "go": go,
        "archive": request.form.get("archive", "") == "1",
        "restore": request.form.get("restore", "") == "1",
    }


def parse_profile_preview():
    """Re-parse the CV for the preview; writes nothing. Returns (data, parsed)."""
    role = request.form.get("role", roles.DEFAULT_ROLE)
    cv_text = request.form.get("cv_text", "")
    parsed = profile_data.parse_cv(cv_text, role)
    # "Add a skill" terms are carried through the preview whether or not they're in
    # the CV; those that ARE get highlighted in the CV block (via the edit context).
    extra = [skills.canonical(t) for t in _split(request.form.get("extra", ""))]
    data = {
        "role": role,
        "cv_text": cv_text,
        "skills": parsed["skills"],
        "extra_skills": extra,
        "notes": request.form.get("notes", ""),
        "seniority": request.form.get("seniority", "") or parsed["seniority"],
        "exclude": _split(request.form.get("exclude", "")),
        "stack": _split(request.form.get("stack", "")),
    }
    return data, parsed


def parse_profile_save() -> dict:
    """The candidate fields (Profile page): role, CV, skills, boundaries. LLM/
    Telegram/schedule live on the Settings page and are parsed separately, so a
    profile save never touches them."""
    picked = [s for s in request.form.getlist("skills") if s.strip()]
    extra = _split(request.form.get("extra", ""))
    return {
        "role": request.form.get("role", roles.DEFAULT_ROLE),
        "cv_text": request.form.get("cv_text", ""),
        "skills": picked,
        "extra_skills": [skills.canonical(t) for t in extra],
        "exclude": _split(request.form.get("exclude", "")),
        "stack": _split(request.form.get("stack", "")),
        "notes": request.form.get("notes", ""),
        "seniority": request.form.get("seniority", ""),
    }


def parse_settings_save() -> dict:
    """The account/output fields (Settings page): LLM access, Telegram, auto-scan.
    Kept apart from the profile fields so each page saves its own half."""
    return {
        "api_key": request.form.get("api_key", "").strip(),
        "llm_model": request.form.get("llm_model", "").strip(),
        **_llm_endpoint(),
        **_telegram_and_schedule(),
    }
