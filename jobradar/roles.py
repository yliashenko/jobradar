#!/usr/bin/env python3
"""
jobradar roles — the scaffold of specializations.

"Who we search for" used to be hardcoded: QA feeds in config.json, QA
boundaries in profile.md. Now it's a choice of role, and a role pulls in three
things:
  - feeds: which DOU queries to send (frontend vacancies aren't in the QA feed);
  - l0:    which reject regexes are relevant (for backend "manual qa" is no criterion);
  - groups: which term groups from skills.py to show and search for in the CV.

A role is a framework, so it lives in git; the choice of role and a specific
person's CV live in profile.json, which git doesn't see. The term dictionary is
shared across all roles (skills.py); a role only picks the relevant groups from
it rather than duplicating them.

Feeds and L0 here are starters, deliberately sparse: they're visible and
editable in the UI, and none of them claims completeness. What matters is
structure, not exhaustiveness.
"""

DOU = "https://jobs.dou.ua/vacancies/feeds/?"
# Djinni via the OFFICIAL RSS (not scraping): one feed per primary_keyword,
# ~100 positions with descriptions. No cap of 25 here like on DOU.
DJINNI = "https://djinni.co/jobs/rss/?"

# Shared rejects: juniors and interns are off-target for any of the roles below.
# Kept separate so we don't copy them into each role and let them drift apart.
_JUNIOR = r"\b(junior|intern|trainee|стажер|джун)\b"
_RELOCATION = r"\brelocation\s+is\s+(required|mandatory)\b"

ROLES = {
    # Feeds are deliberately WIDE — by position, experience and format, without
    # tech keywords. On DOU each feed has a cap of 25, so several orthogonal
    # slices give more coverage than a single query. Depth for specific
    # technologies comes from the "Stack" field in the profile, not the role: the
    # role catches the market, the stack catches you.
    "qa": {
        "label": "QA",
        "feeds": [
            DOU + "category=QA",
            DOU + "category=QA&exp=3-5",
            DOU + "category=QA&remote",
        ],
        "l0": {
            "exclude_title": [_JUNIOR, r"\b(game\s*test|тестувальник\s+ігор)\b"],
            "exclude_text": [_RELOCATION],
            "require_any_text": [
                r"\bQA\b",
                r"\btest(ing|er)?\b",
                r"\bтестув",
                r"\bякост",
            ],
            "min_salary_usd": 2000,
        },
        "groups": ("підходи", "фреймворки", "API", "керування", "мови", "CI/CD"),
        "djinni": [DJINNI + "primary_keyword=QA"],
    },
    "qa_automation": {
        "label": "QA Automation",
        # Wide QA slices + two identifiers of the role itself (SDET/AQA — the
        # name of the profession, not a tech stack) that on DOU reach deeper than
        # the cap. Specific tools (Playwright, pytest…) — via the "Stack" field, not here.
        "feeds": [
            DOU + "category=QA&exp=5plus",
            DOU + "category=QA&exp=3-5",
            DOU + "category=QA&remote",
            DOU + "search=SDET",
            DOU + "search=AQA",
        ],
        "l0": {
            "exclude_title": [
                _JUNIOR,
                r"\b(manual\s+qa|мануальн)\b",
                r"\b(game\s*test|тестувальник\s+ігор)\b",
                r"\b(1c|1с)\b",
            ],
            "exclude_text": [
                _RELOCATION,
                r"\bonly\s+(poland|germany|portugal|spain|cyprus|georgia|tbilisi)-based\b",
                r"\b(tbilisi|warsaw|krakow|lisbon|limassol)-based\s+only\b",
            ],
            "require_any_text": [
                r"\bQA\b",
                r"\bSDET\b",
                r"\bautomation\b",
                r"\bавтоматизац",
                r"\btest(ing|er)?\b",
                r"\bтестув",
            ],
            "min_salary_usd": 3000,
        },
        "groups": (
            "UI-автоматизація",
            "фреймворки",
            "API",
            "мови",
            "AI/ML",
            "CI/CD",
            "підходи",
            "інфраструктура",
            "дані",
            "керування",
        ),
        # Djinni splits QA into separate, non-overlapping primary keywords: "QA"
        # is manual/general, "Automation QA" is its own category (the on-target one
        # for this role). Poll both — "QA" alone silently misses every automation
        # vacancy that isn't cross-posted to DOU.
        "djinni": [
            DJINNI + "primary_keyword=QA",
            DJINNI + "primary_keyword=Automation%20QA",
        ],
    },
    "frontend": {
        "label": "Frontend",
        "feeds": [
            DOU + "category=Front End",
            DOU + "category=Front End&exp=3-5",
            DOU + "category=Front End&remote",
        ],
        "l0": {
            "exclude_title": [_JUNIOR],
            "exclude_text": [_RELOCATION],
            "require_any_text": [
                r"\breact\b",
                r"\bangular\b",
                r"\bvue\b",
                r"\bfront[\s-]?end\b",
                r"\bjavascript\b",
                r"\btypescript\b",
                r"\bверст",
            ],
            "min_salary_usd": 2500,
        },
        "groups": ("фронтенд", "мови", "API", "CI/CD", "підходи", "інфраструктура"),
        "djinni": [DJINNI + "primary_keyword=JavaScript"],
    },
    "backend": {
        "label": "Backend",
        "feeds": [
            DOU + "category=Back End",
            DOU + "category=Back End&exp=3-5",
            DOU + "category=Back End&remote",
        ],
        "l0": {
            "exclude_title": [_JUNIOR],
            "exclude_text": [_RELOCATION],
            "require_any_text": [
                r"\bback[\s-]?end\b",
                r"\bnode\b",
                r"\bpython\b",
                r"\bjava\b",
                r"\bgolang\b",
                r"\b\.net\b",
                r"\bapi\b",
                r"\bмікросервіс",
            ],
            "min_salary_usd": 2500,
        },
        "groups": (
            "бекенд",
            "мови",
            "API",
            "дані",
            "інфраструктура",
            "CI/CD",
            "підходи",
        ),
        "djinni": [DJINNI + "primary_keyword=Python"],
    },
}

DEFAULT_ROLE = "qa_automation"
ROLE_ORDER = ("qa", "qa_automation", "frontend", "backend")


def get(role_key):
    """Role by key; unknown → the default role, so the UI doesn't crash."""
    return ROLES.get(role_key, ROLES[DEFAULT_ROLE])


def label(role_key):
    return get(role_key)["label"]


def feeds(role_key):
    return list(get(role_key)["feeds"])


def l0(role_key):
    # A copy, not a reference: the UI edits a specific profile's L0, not the role's baseline.
    import copy

    return copy.deepcopy(get(role_key)["l0"])


def groups(role_key):
    return get(role_key)["groups"]


def djinni_feeds(role_key):
    return list(get(role_key).get("djinni", []))
