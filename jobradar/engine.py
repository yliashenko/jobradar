"""jobradar.engine — compatibility facade over the split-out core (transitional).

The core is split across jobradar/core/*, jobradar/config.py and
jobradar/cli.py. This module only RE-EXPORTS the public names so that existing
tests and consumers that reference `engine.X` (via `from jobradar import engine
as jobradar`) stay valid during the refactor. Migrating them to direct imports
from core.* is Stage 4 work; then this facade disappears.
"""

from jobradar.cli import cmd_check, cmd_stats, cmd_top, main
from jobradar.config import die, load_config
from jobradar.core import sources
from jobradar.core.collectors.djinni import (
    DJINNI_API,
    collect_djinni,
    djinni_api_details,
)
from jobradar.core.collectors.dou import DOU_TITLE_RE, collect_dou, parse_dou_title
from jobradar.core.collectors.email_alerts import (
    DJINNI_JOB_RE,
    LINKEDIN_JOB_RE,
    AnchorCollector,
    collect_imap,
    decode_header_value,
    enrich_djinni,
    extract_jobs_from_message,
    guess_title_near_link,
    message_html,
    split_title_company,
)
from jobradar.core.db import (
    KEEP_DUPS_FOR_RUNS,
    SCHEMA,
    STATUSES,
    db_connect,
    merge_source,
    meta_get,
    meta_set,
    migrate,
    now_iso,
    run_finish,
    run_start,
)
from jobradar.core.dedup import job_hash, normalize_key
from jobradar.core.filters import SALARY_RE, l0_filter, parse_salary_upper
from jobradar.core.http import USER_AGENT, http_get, http_post_json
from jobradar.core.notify import format_notification, telegram_send
from jobradar.core.pipeline import heartbeat
from jobradar.core.pipeline import run as cmd_run
from jobradar.core.scoring import (
    DEFAULT_MODEL,
    RUBRIC_VERSION,
    SCORER_SYSTEM,
    AnthropicScorer,
    NullScorer,
    build_scorer,
    empty_row,
    load_profile,
    parse_scorer_response,
    score_job,
)
from jobradar.core.text import (
    DESCRIPTION_HTML_LIMIT,
    SAFE_TAGS,
    HtmlSanitizer,
    TagStripper,
    escape,
    parse_feed_date,
    sanitize_html,
    strip_html,
)

__all__ = [
    "DEFAULT_MODEL",
    "DESCRIPTION_HTML_LIMIT",
    "DJINNI_API",
    "DJINNI_JOB_RE",
    "DOU_TITLE_RE",
    "KEEP_DUPS_FOR_RUNS",
    "LINKEDIN_JOB_RE",
    "RUBRIC_VERSION",
    "SAFE_TAGS",
    "SALARY_RE",
    "SCHEMA",
    "SCORER_SYSTEM",
    "STATUSES",
    "USER_AGENT",
    "AnchorCollector",
    "AnthropicScorer",
    "HtmlSanitizer",
    "NullScorer",
    "TagStripper",
    "build_scorer",
    "cmd_check",
    "cmd_run",
    "cmd_stats",
    "cmd_top",
    "collect_djinni",
    "collect_dou",
    "collect_imap",
    "db_connect",
    "decode_header_value",
    "die",
    "djinni_api_details",
    "empty_row",
    "enrich_djinni",
    "escape",
    "extract_jobs_from_message",
    "format_notification",
    "guess_title_near_link",
    "heartbeat",
    "http_get",
    "http_post_json",
    "job_hash",
    "l0_filter",
    "load_config",
    "load_profile",
    "main",
    "merge_source",
    "message_html",
    "meta_get",
    "meta_set",
    "migrate",
    "normalize_key",
    "now_iso",
    "parse_dou_title",
    "parse_feed_date",
    "parse_salary_upper",
    "parse_scorer_response",
    "run_finish",
    "run_start",
    "sanitize_html",
    "score_job",
    "sources",
    "split_title_company",
    "strip_html",
    "telegram_send",
]
