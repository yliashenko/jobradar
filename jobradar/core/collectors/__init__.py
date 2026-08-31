"""Vacancy sources: DOU RSS, Djinni RSS+API, email alerts (Djinni/LinkedIn).

Boards are NOT scraped (CLAUDE.md §3): DOU and Djinni have official RSS, Djinni
and LinkedIn send alerts to email themselves. Each collector reaches the network
through an injected `http` (the real core.http.http_get by default) — so parsers
are tested on RSS fixtures without network (testability requirement #4).
"""
