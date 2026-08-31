"""Provider abstraction (core/llm.py): request shape + response parsing per
provider, transport injected so no network."""

from jobradar.core import llm


def test_anthropic_request_and_parse():
    cap = {}

    def post(url, payload, headers, timeout):
        cap.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {"content": [{"type": "text", "text": "hi"}]}

    out = llm.chat("anthropic", "", "k", "m", "sys", "usr", 100, 30, http_post=post)
    assert out == "hi"
    assert cap["url"] == llm.ANTHROPIC_URL
    assert cap["headers"]["x-api-key"] == "k"
    assert cap["payload"]["system"] == "sys"
    assert cap["payload"]["messages"][0]["content"] == "usr"


def test_openai_request_and_parse():
    cap = {}

    def post(url, payload, headers, timeout):
        cap.update(url=url, payload=payload, headers=headers)
        return {"choices": [{"message": {"content": "yo"}}]}

    out = llm.chat("openai", "", "k", "gpt", "sys", "usr", 100, 30, http_post=post)
    assert out == "yo"
    assert cap["url"].endswith("/chat/completions")
    assert cap["headers"]["Authorization"] == "Bearer k"
    assert [m["role"] for m in cap["payload"]["messages"]] == ["system", "user"]


def test_openai_base_url_override_reaches_local_or_gateway():
    cap = {}

    def post(url, payload, headers, timeout):
        cap["url"] = url
        return {"choices": [{"message": {"content": "x"}}]}

    llm.chat(
        "openai",
        "http://localhost:11434/v1",
        "k",
        "llama",
        "s",
        "u",
        10,
        5,
        http_post=post,
    )
    assert cap["url"] == "http://localhost:11434/v1/chat/completions"


def test_anthropic_base_url_is_a_proxy():
    cap = {}

    def post(url, payload, headers, timeout):
        cap["url"] = url
        return {"content": [{"type": "text", "text": "x"}]}

    llm.chat(
        "anthropic", "https://proxy.test", "k", "m", "s", "u", 10, 5, http_post=post
    )
    assert cap["url"] == "https://proxy.test/v1/messages"


def test_default_provider_is_anthropic():
    cap = {}

    def post(url, payload, headers, timeout):
        cap["url"] = url
        return {"content": [{"type": "text", "text": "x"}]}

    llm.chat("", "", "k", "m", "s", "u", 10, 5, http_post=post)
    assert cap["url"] == llm.ANTHROPIC_URL


def test_openai_empty_choices_is_empty_string():
    out = llm._openai_text({"choices": []})
    assert out == ""
