"""Unit tests for core/cover.py — the cover-letter generator.

The network is injected (http_post), so payload assembly and response parsing are
tested without the API, exactly like the scorer tests.
"""

from jobradar import paths
from jobradar.core import cover


def test_build_posting_text_carries_decode_fields():
    job = {
        "title": "Senior QA Automation",
        "company": "Acme",
        "location": "Kyiv",
        "salary": "$5000",
        "description": "Python, Playwright, pytest.",
    }
    text = cover.build_posting_text(job)
    assert "TITLE: Senior QA Automation" in text
    assert "COMPANY: Acme" in text
    assert "Python, Playwright, pytest." in text


def test_build_posting_text_handles_empty_description():
    job = {
        "title": "QA",
        "company": "",
        "location": "",
        "salary": "",
        "description": "",
    }
    text = cover.build_posting_text(job)
    assert "no description provided" in text
    assert "COMPANY: not specified" in text


def test_parse_cover_response_strips_fence_and_coerces():
    raw = (
        "```json\n"
        '{"letter":"Dear team","evaluation":"E","traceability":"T",'
        '"fit_score":7,"band":"GREEN EDGE"}\n'
        "```"
    )
    out = cover.parse_cover_response(raw)
    assert out["letter"] == "Dear team"
    assert out["evaluation"] == "E"
    assert out["fit_score"] == 7.0
    assert out["band"] == "GREEN EDGE"


def test_parse_cover_response_missing_score_is_none():
    out = cover.parse_cover_response('{"letter":"x"}')
    assert out["fit_score"] is None
    assert out["band"] == ""


def test_parse_cover_response_band_follows_score_not_model():
    # The model sometimes labels a band but glitches the score to 0 (the real
    # "AMBER · 0" bug). The score is authoritative, so the band is re-derived —
    # here 0 → SKIP, never a contradictory AMBER next to 0.
    out = cover.parse_cover_response('{"letter":"x","fit_score":0,"band":"AMBER"}')
    assert out["fit_score"] == 0.0
    assert out["band"] == "SKIP"
    # And a real score overrides a wrong label the other way.
    out2 = cover.parse_cover_response('{"letter":"x","fit_score":7.4,"band":"AMBER"}')
    assert out2["band"] == "GREEN EDGE"


def test_band_for_score_boundaries():
    assert cover.band_for_score(8.5) == "GREEN"
    assert cover.band_for_score(7.0) == "GREEN EDGE"
    assert cover.band_for_score(6.9) == "AMBER"
    assert cover.band_for_score(4.0) == "RED"
    assert cover.band_for_score(3.9) == "SKIP"
    assert cover.band_for_score(None) == ""


def test_parse_cover_response_allows_raw_newlines_in_letter():
    # The model writes a multi-line letter with literal newlines inside the JSON
    # string; strict parsing would reject those control characters.
    raw = '{"letter":"Dear team,\n\nI am writing.","band":"GREEN"}'
    out = cover.parse_cover_response(raw)
    assert out["letter"] == "Dear team,\n\nI am writing."
    assert out["band"] == "GREEN"


def test_generate_cover_builds_payload_and_parses():
    job = {
        "title": "Senior QA",
        "company": "Acme",
        "location": "Kyiv",
        "salary": "$5000",
        "description": "Python and Playwright.",
    }
    captured = {}

    def fake_post(url, payload, headers, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "content": [
                {
                    "type": "text",
                    "text": '{"letter":"Dear team","evaluation":"m",'
                    '"traceability":"t","fit_score":8.5,"band":"GREEN"}',
                }
            ]
        }

    out = cover.generate_cover(
        job,
        "FACTS: 13 years in QA.",
        "secret-key",
        "claude-sonnet-5",
        99,
        http_post=fake_post,
    )
    assert out["letter"] == "Dear team"
    assert out["band"] == "GREEN"
    assert out["fit_score"] == 8.5
    # facts ride in the system prompt, the posting in the user turn.
    assert "FACTS: 13 years in QA." in captured["payload"]["system"]
    assert "Python and Playwright." in captured["payload"]["messages"][0]["content"]
    assert captured["payload"]["model"] == "claude-sonnet-5"
    assert captured["headers"]["x-api-key"] == "secret-key"
    assert captured["timeout"] == 99
    # The API is asked to enforce the JSON shape, so the prose letter can't break
    # hand-escaped quotes/newlines; effort:low keeps thinking shallow (fast) yet
    # present, so the model still computes the fit score. See generate_cover.
    assert captured["payload"]["output_config"]["format"]["type"] == "json_schema"
    assert captured["payload"]["output_config"]["effort"] == "low"


def test_parse_cover_response_empty_is_clear_error():
    import pytest

    with pytest.raises(ValueError, match="empty response"):
        cover.parse_cover_response("")


def test_load_facts_missing_returns_empty(tmp_path):
    paths.use_home(str(tmp_path))
    assert cover.load_facts() == ""


def test_load_facts_reads_and_strips(tmp_path):
    paths.use_home(str(tmp_path))
    with open(paths.career_facts_path(), "w", encoding="utf-8") as fh:
        fh.write("  Yevhen Liashenko, Kyiv.  \n")
    assert cover.load_facts() == "Yevhen Liashenko, Kyiv."


def test_prompt_ships_with_the_code():
    # The distilled craft prompt is a repo resource, always loadable.
    text = cover.load_prompt()
    assert "requirement matrix" in text.lower()
    assert "STRICTLY valid JSON" in text
