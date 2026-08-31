"""L0 — a cheap deterministic filter (regexes + salary threshold).

Runs BEFORE the scorer (CLAUDE.md §3): without it every run would cost tokens on
all records. A rule change is NOT retroactive — the already-filtered sit in the
DB with l0_pass=0 and aren't re-evaluated (§4). SALARY_RE lives here as the
authority on salary parsing; collectors import it to parse titles/descriptions.
"""

import re

SALARY_RE = re.compile(r"\$\s?(\d[\d\s]*)(?:\s*[–—-]\s*\$?\s*(\d[\d\s]*))?")


def parse_salary_upper(text):
    match = SALARY_RE.search(text or "")
    if not match:
        return None

    def to_int(raw):
        digits = re.sub(r"\D", "", raw or "")
        return int(digits) if digits else None

    low = to_int(match.group(1))
    high = to_int(match.group(2))
    values = [v for v in (low, high) if v]
    return max(values) if values else None


def l0_filter(job, rules):
    title = job.get("title", "") or ""
    company = job.get("company", "") or ""
    description = job.get("description", "") or ""
    haystack_title = title.lower()
    haystack_all = (title + " " + company + " " + description).lower()

    for pattern in rules.get("exclude_title", []):
        if re.search(pattern, haystack_title, re.I):
            return False, f"title matched exclude: {pattern}"
    for pattern in rules.get("exclude_text", []):
        if re.search(pattern, haystack_all, re.I):
            return False, f"text matched exclude: {pattern}"

    require = rules.get("require_any_text", [])
    if require and not any(re.search(p, haystack_all, re.I) for p in require):
        return False, "no match for require_any_text"

    floor = rules.get("min_salary_usd")
    if floor:
        upper = parse_salary_upper(job.get("salary", "") or title)
        if upper is not None and upper < int(floor):
            return False, f"salary cap ${upper} below floor ${int(floor)}"
    return True, ""
