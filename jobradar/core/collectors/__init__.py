"""Vacancy sources: DOU RSS and Djinni RSS+API.

Boards are NOT scraped (CLAUDE.md §3): DOU and Djinni have official RSS. Each
collector reaches the network through an injected `http` (the real
core.http.http_get by default) — so parsers are tested on RSS fixtures without
network (testability requirement #4).
"""
