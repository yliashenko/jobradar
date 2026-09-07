#!/usr/bin/env python3
"""
jobradar profile — the dynamic candidate profile.

Replaces the hardcoded profile.md: role, CV text, confirmed skills and the free
"boundaries/caveats" block live in profile.json. This is personal data — git
doesn't see it (like config.json and jobs.db).

The division of labor with the scorer is deliberate and important:
  - parse_cv pulls a FLAT list of tags from the CV — it feeds the feed FILTER;
  - the notes block (free text) feeds the SCORER.
The flat list lies about depth: "Python" in the CV becomes a tag, but the scorer
must know it's LLM code that was curated, not written. So the honesty of the
score rests on notes, not on the skill list. Don't blur these two roles.
"""

import json
import os
import re
import urllib.parse

from jobradar import paths, roles, skills

# Paths to profile.json/.md go through paths (overridden by JOBRADAR_HOME in tests).

# Seniority is taken from the EARLIEST mention in the text, not by rank: in a CV
# the title is the first line ("Senior QA … as a lead" is Senior, not Lead),
# while "mentoring juniors" is mentioned later and must not beat the heading.
_SENIORITY = (
    ("Principal", r"\bprincipal\b"),
    ("Lead", r"\b(tech\s*lead|team\s*lead|teamlead|lead)\b"),
    ("Senior", r"\bsenior\b|\bстарший\b"),
    ("Middle", r"\bmiddle\b|\bмідл\b"),
    ("Junior", r"\bjunior\b|\bджун"),
)
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|роки|років|рік|yrs)", re.I)


def default_profile():
    return {
        "role": roles.DEFAULT_ROLE,
        "cv_text": "",
        "skills": [],
        # Skills you deliberately add that need NOT be in the CV — universal,
        # assumed-standard ones (Scrum, HTTP) few people spell out. Unlike
        # "skills", these are not validated against the CV.
        "extra_skills": [],
        "stack": [],
        "exclude": [],
        "notes": "",
        "seniority": "",
        # Own LLM access so the tool runs on the user's account (portability): an
        # API key powers all LLM features (scoring + cover letters); llm_model is the
        # cover-letter model; llm_provider/llm_base_url pick Anthropic (default) or an
        # OpenAI-compatible endpoint (a gateway or a local Ollama). Priority over
        # config.json; personal data — never leaves profile.json.
        "api_key": "",
        "llm_model": "",
        "llm_provider": "",
        "llm_base_url": "",
        # Telegram output channel — the SINGLE source for these settings (config.json
        # no longer carries a telegram section). bot_token from @BotFather, chat_id
        # from getUpdates once you've messaged the bot; personal data, never committed.
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        # Master switch for the bot: off → scans still score & store, nothing is
        # pushed to Telegram (heartbeat included). notify_min_score is the minimum
        # score that gets pushed ("" = the built-in default of 7); heartbeat_alert_hours
        # is the silence window before the "nothing new" alert (kept — CLAUDE.md §4).
        "telegram_enabled": True,
        "notify_min_score": "",
        "heartbeat_alert_hours": 24,
        # In-process auto-scan: fires only while `serve` is up (it is not a system
        # service). Reminder-style cadence — `schedule_repeat` is the rhythm (one of
        # SCHEDULE_REPEATS), `schedule_hour` the anchor hour (every-6h at 8 fires
        # 08,14,20,02). `schedule_weekday` (0=Mon) applies to weekly/biweekly,
        # `schedule_monthday` (1–28) to monthly. Shares the run lock with the button.
        "schedule_enabled": False,
        "schedule_repeat": "daily",
        "schedule_hour": 9,
        "schedule_weekday": 0,
        "schedule_monthday": 1,
    }


# Auto-scan cadences, canonical order (drives the Settings dropdown via the web
# layer's SCHEDULE_REPEAT_LABELS). Keys are the stored values; save() clamps to
# this set so an unknown repeat can't slip in and silently never fire.
SCHEDULE_REPEATS = (
    "every_6h",
    "every_12h",
    "daily",
    "weekday",
    "weekly",
    "biweekly",
    "monthly",
)


def _clamp_int(value, low, high, default):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def load():
    """Profile from disk or an empty default. Broken JSON doesn't crash the UI."""
    if not os.path.exists(paths.profile_json_path()):
        return default_profile()
    try:
        with open(paths.profile_json_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return default_profile()
    merged = default_profile()
    merged.update({k: data[k] for k in merged if k in data})
    if merged["role"] not in roles.ROLES:
        merged["role"] = roles.DEFAULT_ROLE
    return merged


def save(data):
    """Atomic write: write to a temp file and rename, so a cut-off write doesn't
    leave half a profile that can't be recovered from."""
    clean = default_profile()
    clean.update({k: data.get(k, clean[k]) for k in clean})
    if clean["role"] not in roles.ROLES:
        clean["role"] = roles.DEFAULT_ROLE
    # A skill stays only if it's in the CV text — the CV is the source of truth,
    # not a separate list that drifts from it.
    clean["skills"] = validate_skills(
        [s for s in clean.get("skills", []) if str(s).strip()], clean.get("cv_text", "")
    )
    # Hand-added skills that need NOT be in the CV (Scrum, HTTP…). Canonicalize
    # and dedupe like exclude/stack; also drop any already confirmed from the CV
    # so a skill isn't listed twice. Deliberately not validated against the CV.
    have = {s.lower() for s in clean["skills"]}
    extra = []
    for term in clean.get("extra_skills", []):
        canon = skills.canonical(str(term).strip())
        if canon and canon.lower() not in have:
            have.add(canon.lower())
            extra.append(canon)
    clean["extra_skills"] = extra
    # "Not for me" are anti-goals; they must NOT be in the CV, so we don't
    # validate against it — just canonicalize the spelling and drop duplicates.
    seen, excl = set(), []
    for term in clean.get("exclude", []):
        canon = skills.canonical(str(term).strip())
        if canon and canon.lower() not in seen:
            seen.add(canon.lower())
            excl.append(canon)
    clean["exclude"] = excl
    # "Stack" are the skills that add DEEP search feeds. Not validated against
    # the CV: you can put here what you're aiming for, not only what you already know.
    seen, stack = set(), []
    for term in clean.get("stack", []):
        term = str(term).strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            stack.append(term)
    clean["stack"] = stack
    # Auto-scan schedule: keep the cadence a known key and the hour/day fields in
    # range, so a hand-edited or stale profile can't feed the scheduler a slot it
    # would never match (which reads exactly like a silently-broken schedule).
    if clean["schedule_repeat"] not in SCHEDULE_REPEATS:
        clean["schedule_repeat"] = "daily"
    clean["schedule_hour"] = _clamp_int(clean["schedule_hour"], 0, 23, 9)
    clean["schedule_weekday"] = _clamp_int(clean["schedule_weekday"], 0, 6, 0)
    clean["schedule_monthday"] = _clamp_int(clean["schedule_monthday"], 1, 28, 1)
    tmp = paths.profile_json_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, paths.profile_json_path())
    return clean


def present_in_cv(term, cv_text):
    """Whether the term is in the CV text as a standalone word.

    For dictionary terms — via skills.mentions (so Go/SAFe stay case-sensitive).
    For custom, hand-added ones — a simple word boundary: this lets you add a
    skill the dictionary doesn't know but the CV has (a niche tool, a rare
    framework). "Java" won't survive via "JavaScript" — word boundary, not substring.
    """
    if term.lower() in skills.CANONICAL:
        return skills.mentions(cv_text, term)
    pattern = re.compile(rf"(?<![\w#+]){re.escape(term)}(?![\w#+])", re.I)
    return bool(pattern.search(cv_text or ""))


def validate_skills(skill_list, cv_text):
    """Keeps only the skills that are actually in the CV text.

    The CV is the source of truth about skills. This filters out the stale (a
    skill left in the profile but removed from the CV) and the randomly added.
    But something added that is REALLY in the CV stays — even if the dictionary
    doesn't know it.
    """
    seen = []
    for term in skill_list:
        canon = skills.canonical(term)
        if canon.lower() in {s.lower() for s in seen}:
            continue
        if present_in_cv(canon, cv_text):
            seen.append(canon)
    return seen


def parse_cv(cv_text, role_key):
    """CV + role → a structure for display and editing.

    Skills are grouped by the role's groups and in its order: for a frontender
    React matters more than SQL, for a backender the other way round. Terms
    outside the role's groups aren't dropped but pushed to the end — a CV is
    often wider than a single role.
    """
    found = skills.found_terms(cv_text)
    role_groups = roles.groups(role_key)
    order = {name: i for i, name in enumerate(role_groups)}

    by_group = {}
    for term in found:
        canon = skills.canonical(term)
        group = skills.GROUP_OF.get(canon.lower(), "")
        by_group.setdefault(group, [])
        if canon not in by_group[group]:
            by_group[group].append(canon)

    # Role groups first, then the rest (so what's seen in the CV doesn't vanish).
    grouped = []
    for name in role_groups:
        if by_group.get(name):
            grouped.append((name, by_group[name]))
    for name, terms in by_group.items():
        if name and name not in order and terms:
            grouped.append((name, terms))

    flat = [t for _, terms in grouped for t in terms]
    return {
        "grouped": grouped,
        "skills": flat,
        "seniority": _detect_seniority(cv_text),
        "years": _detect_years(cv_text),
    }


def _detect_seniority(text):
    low = (text or "").lower()
    best, best_pos = "", len(low) + 1
    for label, pattern in _SENIORITY:
        m = re.search(pattern, low, re.I)
        if m and m.start() < best_pos:
            best, best_pos = label, m.start()
    return best


def _detect_years(text):
    nums = [int(m) for m in _YEARS.findall(text or "") if int(m) <= 40]
    return max(nums) if nums else 0


def scorer_text(data=None):
    """What the scorer sees. Priority — profile.json; fallback — profile.md.

    The scorer gets the CV, confirmed skills, seniority AND the boundaries/caveats
    block. It's the boundaries that set this text apart from a bare CV — without
    them the score turns optimistic again.
    """
    data = data if data is not None else load()
    if not data.get("cv_text") and not data.get("notes"):
        if os.path.exists(paths.profile_md_path()):
            with open(paths.profile_md_path(), encoding="utf-8") as fh:
                return fh.read().strip()
        return ""

    parts = ["Role we're scoring for: {}.".format(roles.label(data.get("role")))]
    if data.get("seniority"):
        parts.append("Level: {}.".format(data["seniority"]))
    confirmed = list(data.get("skills") or []) + list(data.get("extra_skills") or [])
    if confirmed:
        parts.append("Confirmed skills: {}.".format(", ".join(confirmed)))
    if data.get("notes"):
        parts.append(
            "\nBoundaries & caveats (treat as GAP, not PARTIAL):\n{}".format(
                data["notes"]
            )
        )
    if data.get("cv_text"):
        parts.append("\nFull CV text:\n{}".format(data["cv_text"]))
    return "\n".join(parts).strip()


def effective_feeds(cfg, data=None):
    """Feeds for a run: broad role-based ones + deep "Stack" ones.

    The role catches the market by position (broadly), the "Stack" picks up depth
    for your skills — each gives a separate window of 25 and gets past the DOU cap
    exactly on what matters to you. Without a profile — the old behavior (config.json).
    """
    data = data if data is not None else load()
    if not os.path.exists(paths.profile_json_path()):
        return (cfg.get("sources", {}).get("dou", {}) or {}).get("feeds", [])
    feeds = roles.feeds(data.get("role"))
    for term in data.get("stack", []):
        feeds.append(roles.DOU + "search=" + urllib.parse.quote(term))
    # Drop duplicates, keep order: the stack may repeat what's already in the role.
    seen, unique = set(), []
    for f in feeds:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def effective_djinni_feeds(cfg, data=None):
    """Djinni feeds for a run: role-based if a profile is set; otherwise config.json."""
    data = data if data is not None else load()
    if os.path.exists(paths.profile_json_path()):
        return roles.djinni_feeds(data.get("role"))
    return (cfg.get("sources", {}).get("djinni", {}) or {}).get("feeds", [])


def effective_l0(cfg, data=None):
    """L0 for a run: role-based (or from config.json), plus the profile's anti-goals.

    "Not for me" filters vacancies out like Junior does — but only by TITLE,
    deliberately conservative: "manual testing" in the description of an
    automation role is one of the duties, and such a vacancy must not be cut;
    "Manual Testing Engineer" in the title is another matter.
    """
    data = data if data is not None else load()
    base = (
        roles.l0(data.get("role"))
        if os.path.exists(paths.profile_json_path())
        else dict(cfg.get("l0", {}))
    )
    excl = data.get("exclude", [])
    if excl:
        base = dict(base)
        titles = list(base.get("exclude_title", []))
        titles += [rf"(?<![\w#+]){re.escape(t)}(?![\w#+])" for t in excl]
        base["exclude_title"] = titles
    return base
