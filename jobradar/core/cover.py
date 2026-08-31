"""Cover letter + fit evaluation for an applied vacancy (mirrors core/scoring.py).

One Anthropic call turns a stored posting into the three blocks the
`work-cv-cover-letter` skill produces: a fit evaluation, the letter itself, and a
traceability map. The skill normally chains `work-position-evaluation` and reads
files as an agent; here the posting already lives in the DB (nothing to fetch) and
the candidate facts are supplied verbatim, so the whole pipeline distils into one
prompt (prompts/cover_letter.md).

Two deliberate seams, both like the scorer:
  - the network call is injected (http_post) so response parsing is tested
    without the API;
  - the candidate facts come from career-facts.md in HOME (paths.career_facts_path),
    NOT from profile.json. The skill treats career-facts.md as its only source of
    truth; the scorer keeps its own profile. Facts are never invented — a missing
    file means no letter, not a guessed one.
"""

import json
import os
import re

from jobradar import paths
from jobradar.core import llm

DEFAULT_MODEL = "claude-sonnet-5"
# Budget for shallow (effort:low) thinking plus the JSON output — letter +
# evaluation + traceability. That fits in a few thousand tokens; the headroom just
# avoids a mid-letter cut on a long posting. A big cap here is what let default
# high-effort thinking run past the request timeout, so keep it modest.
MAX_TOKENS = 8000

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "cover_letter.md")

# The response shape, enforced by the API (output_config.format). The letter is
# multi-line prose full of quotes and newlines; a model hand-formatting it into a
# JSON string reliably breaks the escaping. A schema makes the API emit valid JSON.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "letter": {"type": "string"},
        "evaluation": {"type": "string"},
        "traceability": {"type": "string"},
        "fit_score": {"type": "number"},
        "band": {"type": "string"},
    },
    "required": ["letter", "evaluation", "traceability", "fit_score", "band"],
    "additionalProperties": False,
}


def load_prompt():
    """The distilled craft prompt (how to write), shipped with the code."""
    with open(_PROMPT_PATH, encoding="utf-8") as fh:
        return fh.read()


def load_facts():
    """The candidate facts (what is true): career-facts.md in HOME, '' if absent."""
    path = paths.career_facts_path()
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def build_posting_text(job):
    """The posting as the model reads it: decode fields + the flat description."""
    return "\n".join(
        [
            "TITLE: " + (job["title"] or ""),
            "COMPANY: " + (job["company"] or "not specified"),
            "LOCATION: " + (job["location"] or "not specified"),
            "SALARY: " + (job["salary"] or "not specified"),
            "DESCRIPTION:",
            (job["description"] or "no description provided")[:8000],
        ]
    )


# Fit-score bands (prompts/cover_letter.md): the lower bound of each, high to low.
# The band is DERIVED from the score here, not read from the model — the two are
# generated independently and occasionally disagree (a real "AMBER" band next to a
# glitched 0 score). The prompt's own rule is "report the arithmetic", so the score
# wins and the band follows it, which also makes an "AMBER · 0" badge impossible.
_BANDS = ((8.5, "GREEN"), (7.0, "GREEN EDGE"), (5.5, "AMBER"), (4.0, "RED"))


def band_for_score(score):
    """Fit band for a numeric score, or '' when there is no score."""
    if score is None:
        return ""
    for low, name in _BANDS:
        if score >= low:
            return name
    return "SKIP"


def parse_cover_response(text):
    """LLM response text (possibly fenced) → the saved cover-letter row."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        # No text block came back — usually the model hit max_tokens while still
        # thinking. Say so plainly instead of a bare "Expecting value" from json.
        raise ValueError("the model returned an empty response (likely truncated)")
    # strict=False: the letter is a multi-line string and the model emits real
    # newlines inside it rather than \n escapes — the default parser rejects those.
    parsed = json.loads(text, strict=False)
    score = parsed.get("fit_score")
    fit = float(score) if isinstance(score, (int, float)) else None
    # No score → fall back to the model's own band label rather than blanking it.
    band = (
        band_for_score(fit) if fit is not None else str(parsed.get("band", "")).strip()
    )
    return {
        "letter": str(parsed.get("letter", "")).strip(),
        "evaluation": str(parsed.get("evaluation", "")).strip(),
        "traceability": str(parsed.get("traceability", "")).strip(),
        "fit_score": fit,
        "band": band,
    }


def generate_cover(
    job,
    facts,
    api_key,
    model,
    timeout,
    http_post=None,
    provider="anthropic",
    base_url="",
):
    """One LLM call: posting + facts → {letter, evaluation, traceability, ...}.

    `facts` (career-facts.md) rides in the system prompt as the only source of
    truth; the posting is the user turn. provider/base_url pick Anthropic (default)
    or an OpenAI-compatible endpoint. Mirrors scoring.score_job.
    """
    system = (
        load_prompt()
        + "\n\n# CANDIDATE FACTS (the only source of truth)\n\n"
        + (facts or "")
    )
    text = llm.chat(
        provider,
        base_url,
        api_key,
        model,
        system=system,
        user=build_posting_text(job),
        max_tokens=MAX_TOKENS,
        timeout=timeout,
        http_post=http_post,
        # effort:low keeps adaptive thinking shallow — enough to actually compute
        # the fit score (fully disabling it let the model skip the arithmetic and
        # emit a 0), but fast enough that the non-streaming call stays well under
        # the timeout. format makes the API guarantee schema-valid JSON, so the
        # letter's prose can't break hand-escaped quotes and newlines.
        output_config={
            "format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA},
            "effort": "low",
        },
    )
    return parse_cover_response(text)
