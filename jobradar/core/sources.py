"""Registry of sources: what to collect this run (testability requirement #4).

The pipeline doesn't know about specific boards — it calls collect(cfg).
build_sources reads config and returns a list of sources (each a callable
(report) -> [job]). For tests/e2e there's a fixture source:
`sources.fixture = {"enabled": true, "path": …}` turns on reading ready-made
vacancies from a JSON file instead of the network, and e2e seeds the app a known
set without any IMAP/RSS.
"""

import json
import logging
from functools import partial

from jobradar.core.collectors import djinni, dou, email_alerts

log = logging.getLogger("jobradar")


def _fixture_source(path):
    """Source from a JSON file {"jobs": [ {source,url,title,...}, … ]} (e2e/test)."""

    def collect(report=None):
        try:
            with open(path, encoding="utf-8") as fh:
                jobs = json.load(fh).get("jobs", [])
        except (OSError, ValueError) as exc:
            log.error("Fixture source %s failed to read: %s", path, exc)
            jobs = []
        if report is not None:
            report.append({"feed": f"fixture: {path}", "count": len(jobs), "error": ""})
        return jobs

    return collect


def _imap_source(imap_cfg, delay, http):
    def collect(report=None):
        jobs = email_alerts.collect_imap(
            imap_cfg,
            fetch_djinni_pages=bool(imap_cfg.get("fetch_djinni_pages", True)),
            request_delay=delay,
            http=http,
        )
        if report is not None:
            report.append(
                {
                    "feed": f"email: folder {imap_cfg.get('folder', '')}",
                    "count": len(jobs),
                    "error": "",
                }
            )
        return jobs

    return collect


def build_sources(cfg, http=None):
    """List of active sources per config. Each a callable (report) -> [job]."""
    sources_cfg = cfg.get("sources", {})

    fixture = sources_cfg.get("fixture", {})
    if fixture.get("enabled"):
        # The fixture replaces the whole network: e2e/test seeds a known set of vacancies.
        return [_fixture_source(fixture["path"])]

    delay = float(cfg.get("request_delay_seconds", 2))
    out = []

    dou_cfg = sources_cfg.get("dou", {})
    if dou_cfg.get("enabled"):
        out.append(partial(dou.collect_dou, dou_cfg.get("feeds", []), http=http))

    djinni_cfg = sources_cfg.get("djinni", {})
    if djinni_cfg.get("enabled"):
        out.append(
            partial(
                djinni.collect_djinni,
                djinni_cfg.get("feeds", []),
                request_delay=delay,
                enrich=bool(djinni_cfg.get("enrich", True)),
                http=http,
            )
        )

    imap_cfg = sources_cfg.get("imap", {})
    if imap_cfg.get("enabled"):
        out.append(_imap_source(imap_cfg, delay, http))

    return out


def collect(cfg, report=None, http=None):
    """Collect from all active sources. report accumulates a row per feed (/runs)."""
    jobs = []
    for source in build_sources(cfg, http=http):
        jobs.extend(source(report))
    return jobs
