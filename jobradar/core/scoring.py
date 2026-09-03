"""L1 — score a vacancy against the profile via the Anthropic API (ADR-0003 §3).

Runs only on what passed L0 (to save tokens). A score is NEVER recomputed
(CLAUDE.md §3.4): LLMs drift, and the same vacancy would get different marks on
different days. If you change the rubric in SCORER_SYSTEM or the profile facts,
bump RUBRIC_VERSION.

The scorer is SWAPPABLE (testability requirement #3): the pipeline calls
scorer.score(job), and build_scorer decides what it is from config: NullScorer
(disabled, no score), LlmScorer (network — Anthropic or an OpenAI-compatible
provider via core.llm), or a fake with a fixed mark in tests. The network call
score_job is injected too (http_post), so response parsing is tested without the
API.
"""

import json
import logging
import re
import time

from jobradar.core import llm

log = logging.getLogger("jobradar")

RUBRIC_VERSION = "v2"
# L1 scoring runs on EVERY vacancy that passes L0, so its default model is cheap/fast
# and chosen per provider. Overridable via config.json `scorer.model` (blank = auto).
DEFAULT_SCORER_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}
DEFAULT_MODEL = DEFAULT_SCORER_MODELS["anthropic"]  # back-compat alias (Anthropic)
API_URL = "https://api.anthropic.com/v1/messages"


def default_scorer_model(provider):
    """The cheap default scoring model for a provider (Anthropic → Haiku, OpenAI →
    gpt-4o-mini). Unknown provider falls back to the Anthropic default."""
    return DEFAULT_SCORER_MODELS.get(provider, DEFAULT_MODEL)


SCORER_SYSTEM = """You are scoring how well a candidate fits a vacancy. Below are verified facts about the candidate.

{profile}

SCORING RULES:
- Score only from the facts above. Do not infer or add skills the candidate doesn't have.
- score: a number from 0 to 10 in steps of 0.5.
  9-10: almost full match on stack and level.
  7-8.5: strong match, 1-2 gaps that close within weeks.
  5-6.5: half the stack matches, with a structural gap (language, domain, level).
  0-4.5: not his position.
- If the vacancy requires something the candidate clearly does NOT have (a different
  programming language as the primary one, relocation, a domain with a hard experience
  requirement) — that is a GAP, not a PARTIAL.
- band: one of "strong", "worth_trying", "stretch", "skip".
- matched: up to 4 short bullets on what exactly he covers.
- gaps: up to 3 short bullets, the costliest gaps first.
- verdict: one sentence in English, no pleasantries, to the point.

Respond with STRICTLY valid JSON, no markdown fence, in the format:
{{"score": 7.5, "band": "worth_trying", "matched": ["..."], "gaps": ["..."], "verdict": "..."}}"""


def empty_row():
    """A "no score" row — when the scorer is disabled or failed."""
    return {"score": None, "band": "", "matched": [], "gaps": [], "verdict": ""}


def parse_scorer_response(text):
    """LLM response text (possibly in a markdown fence) → a score row.

    Split out from the network so JSON/fence parsing is tested without the API.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    return {
        "score": float(parsed.get("score", 0)),
        "band": str(parsed.get("band", "")),
        "matched": list(parsed.get("matched", []))[:4],
        "gaps": list(parsed.get("gaps", []))[:3],
        "verdict": str(parsed.get("verdict", "")),
    }


def score_job(
    job,
    api_key,
    model,
    profile,
    timeout,
    http_post=None,
    provider="anthropic",
    base_url="",
):
    job_text = "\n".join(
        [
            "TITLE: " + job["title"],
            "COMPANY: " + (job["company"] or "not specified"),
            "LOCATION: " + (job["location"] or "not specified"),
            "SALARY: " + (job["salary"] or "not specified"),
            "DESCRIPTION:",
            (
                job["description"]
                or "no description, score by the title only and set score no higher than 6"
            )[:6000],
        ]
    )
    text = llm.chat(
        provider,
        base_url,
        api_key,
        model,
        system=SCORER_SYSTEM.format(profile=profile),
        user=job_text,
        max_tokens=700,
        timeout=timeout,
        http_post=http_post,
    )
    return parse_scorer_response(text)


class NullScorer:
    """Scorer disabled: no score — everyone who passed L0 gets notified."""

    def score(self, job):
        return empty_row()


class LlmScorer:
    """The real scorer: one LLM call per vacancy, fail-safe on error. provider and
    base_url let it run on Anthropic (default) or an OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key,
        model,
        profile,
        timeout,
        request_delay=0.0,
        http_post=None,
        provider="anthropic",
        base_url="",
    ):
        self.api_key = api_key
        self.model = model
        self.profile = profile
        self.timeout = timeout
        self.request_delay = request_delay
        self.http_post = http_post
        self.provider = provider
        self.base_url = base_url

    def score(self, job):
        try:
            row = score_job(
                job,
                self.api_key,
                self.model,
                self.profile,
                self.timeout,
                http_post=self.http_post,
                provider=self.provider,
                base_url=self.base_url,
            )
        except Exception as exc:
            log.error("Scoring failed for %r: %s", (job.get("title") or "")[:60], exc)
            return empty_row()
        if self.request_delay:
            time.sleep(self.request_delay)
        return row


# Back-compat alias: the class was Anthropic-only before providers were added.
AnthropicScorer = LlmScorer


def llm_settings():
    """(provider, base_url, api_key) for every LLM feature — scoring and cover
    letters share the account and provider; only the MODEL differs (scorer.model
    for L1, profile.llm_model for the letter).

    The account lives ONLY in the profile (Settings page): there is no config.json
    or environment fallback, so there is a single place to see and set the key.
    """
    from jobradar import candidate

    prof = candidate.load()
    provider = prof.get("llm_provider") or "anthropic"
    base_url = prof.get("llm_base_url", "")
    api_key = prof.get("api_key", "")
    return provider, base_url, api_key


def effective_api_key():
    """Just the key (profile only). See llm_settings for the full set."""
    return llm_settings()[2]


def build_scorer(cfg, profile="", http_post=None):
    """Scorer from config: the real one (enabled + key) or NullScorer."""
    sc = cfg.get("scorer", {})
    provider, base_url, api_key = llm_settings()
    if sc.get("enabled") and api_key:
        return LlmScorer(
            api_key,
            sc.get("model") or default_scorer_model(provider),
            profile,
            int(sc.get("timeout_seconds", 60)),
            request_delay=float(cfg.get("request_delay_seconds", 2)),
            http_post=http_post,
            provider=provider,
            base_url=base_url,
        )
    return NullScorer()


def load_profile():
    """Text for the scorer: the dynamic profile.json, falling back to profile.md."""
    from jobradar import candidate
    from jobradar.config import die

    text = candidate.scorer_text()
    if not text:
        die(
            "Neither profile.json nor profile.md exists — the scorer has nothing to work with."
        )
    return text
