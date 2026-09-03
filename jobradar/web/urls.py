"""URL/query builders that preserve filter state across navigation.

One tag cycles three states in a single link (none → in filter → excluded →
none), like Apple Notes: no separate add/exclude buttons, the tag stays one
object. Query keys are ordered fixed so links don't shimmer.
"""

import urllib.parse

from jobradar import skills


def tech_sets(params):
    """Tags switched into the filter, and tags excluded from it."""

    def parse(name):
        raw = (params or {}).get(name, "")
        return [skills.canonical(t) for t in raw.split(",") if t.strip()]

    return parse("tech"), parse("notech")


def co_sets(params):
    """Companies chosen into the filter. Separator is newline (a company name may
    contain a comma, but not a newline)."""
    raw = (params or {}).get("co", "")
    return [c for c in raw.split("\n") if c.strip()]


def tech_url(params, included, excluded, path="/"):
    """URL with a given tag set. Key order is fixed."""
    query = {"status": (params or {}).get("status", "all")}
    if included:
        query["tech"] = ",".join(included)
    if excluded:
        query["notech"] = ",".join(excluded)
    for key in ("source", "q", "min", "l0", "token", "co", "sort", "days"):
        if (params or {}).get(key):
            query[key] = params[key]
    return path + "?" + urllib.parse.urlencode(query)


def tech_href(term, params=None, path="/"):
    """A tag's next state on click: none → in filter → excluded → none."""
    params = params or {}
    term = skills.canonical(term)
    included, excluded = tech_sets(params)
    if term in included:
        included = [t for t in included if t != term]
        excluded = [*excluded, term]
    elif term in excluded:
        excluded = [t for t in excluded if t != term]
    else:
        included = [*included, term]
    return tech_url(params, included, excluded, path)


def tech_drop_href(term, params, path="/"):
    """Remove a tag entirely, without cycling through the full state loop."""
    term = skills.canonical(term)
    included, excluded = tech_sets(params)
    return tech_url(
        params,
        [t for t in included if t != term],
        [t for t in excluded if t != term],
        path,
    )


def tech_state(term, params):
    included, excluded = tech_sets(params)
    term = skills.canonical(term)
    if term in included:
        return "on"
    return "off" if term in excluded else ""


def build_query(params, **overrides):
    merged = {k: v for k, v in params.items() if v not in ("", None)}
    for key, value in overrides.items():
        if value in ("", None):
            merged.pop(key, None)
        else:
            merged[key] = value
    return urllib.parse.urlencode(merged)


def feed_link(params, **overrides):
    """Link into the feed keeping filters, dropping page-specific params."""
    clean = {k: v for k, v in params.items() if k != "run"}
    return "/?" + build_query(clean, **overrides)


def company_link(company, params=None):
    """Link to a company page. Carry the token so access isn't lost."""
    query = {"name": company}
    token = (params or {}).get("token", "")
    if token:
        query["token"] = token
    return "/company?" + urllib.parse.urlencode(query)


def page_link(path, params):
    """Move between pages keeping the chosen tags and token."""
    included, excluded = tech_sets(params)
    if not included and not excluded and not co_sets(params):
        token = (params or {}).get("token", "")
        return path + (("?token=" + urllib.parse.quote(token)) if token else "")
    return tech_url(params, included, excluded, path)


def calendar_link(params, year, month):
    query = {"year": year, "month": month}
    token = (params or {}).get("token", "")
    if token:
        query["token"] = token
    return "/calendar?" + urllib.parse.urlencode(query)


def profile_link(edit, token):
    return _page_edit_link("/profile", edit, token)


def settings_link(edit, token):
    return _page_edit_link("/settings", edit, token)


def _page_edit_link(path, edit, token):
    query = {}
    if edit:
        query["edit"] = "1"
    if token:
        query["token"] = token
    return path + ("?" + urllib.parse.urlencode(query) if query else "")
