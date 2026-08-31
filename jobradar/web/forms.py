"""Parse POST form data into the shapes the domain expects."""

import re

from flask import request

from jobradar import candidate as profile_data
from jobradar import roles, skills
from jobradar.web.constants import HIRING_LABELS


def _split(value: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,\n]", value or "") if t.strip()]


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
        # Carried through the preview round-trip so a skill re-detect doesn't wipe them.
        "api_key": request.form.get("api_key", "").strip(),
        "llm_model": request.form.get("llm_model", "").strip(),
        "llm_provider": request.form.get("llm_provider", "").strip(),
        "llm_base_url": request.form.get("llm_base_url", "").strip(),
    }
    return data, parsed


def parse_profile_save() -> dict:
    """Confirmed checkboxes plus manually added skills."""
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
        "api_key": request.form.get("api_key", "").strip(),
        "llm_model": request.form.get("llm_model", "").strip(),
        "llm_provider": request.form.get("llm_provider", "").strip(),
        "llm_base_url": request.form.get("llm_base_url", "").strip(),
    }
