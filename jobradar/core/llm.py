"""Provider-agnostic single-shot LLM call.

The scorer (L1) and the cover-letter generator both need "system + one user turn
→ text". This is the one place that knows how each provider encodes that, so
neither has to re-implement it:

  - "anthropic" (default): the Messages API (x-api-key, system + messages,
    content[].text). A base_url points at an Anthropic-compatible proxy.
  - "openai": the Chat Completions schema (Authorization: Bearer, messages with a
    system role, choices[].message.content). This is also how a local Ollama or
    any OpenAI-compatible gateway is reached — just set base_url.

The transport (http_post) is injected, so both providers are tested without the
network.
"""

from jobradar.core.http import http_post_json

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_BASE = "https://api.openai.com/v1"


def chat(
    provider,
    base_url,
    api_key,
    model,
    system,
    user,
    max_tokens,
    timeout,
    http_post=None,
    thinking=None,
    output_config=None,
):
    """One call → the assistant's text. Provider decides URL/auth/shape.

    `thinking` (Anthropic only) sets the request's thinking config, e.g.
    {"type": "disabled"} to turn off the models that think by default (Sonnet 5,
    Opus 5). Omitted → the provider default. Ignored for the OpenAI shape.

    `output_config` (Anthropic only) constrains the response format, e.g. a
    {"format": {"type": "json_schema", "schema": {...}}} so the reply is
    schema-valid JSON the API guarantees — no hand-escaping bugs. Ignored for
    the OpenAI shape.
    """
    post = http_post or http_post_json
    provider = (provider or "anthropic").strip().lower()
    base_url = (base_url or "").strip().rstrip("/")

    if provider == "openai":
        url = (base_url or OPENAI_BASE) + "/chat/completions"
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        }
        return _openai_text(post(url, payload, headers, timeout=timeout))

    # Anthropic (default). A base_url is an Anthropic-compatible proxy.
    url = (base_url + "/v1/messages") if base_url else ANTHROPIC_URL
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if thinking is not None:
        payload["thinking"] = thinking
    if output_config is not None:
        payload["output_config"] = output_config
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    return _anthropic_text(post(url, payload, headers, timeout=timeout))


def _anthropic_text(data):
    return "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )


def _openai_text(data):
    choices = data.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content") or ""
