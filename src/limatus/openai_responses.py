"""OpenAI Responses API with structured (JSON Schema) output, for rewrite suggestions."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ResponseTruncationError(RuntimeError):
    """The model stopped before completing the requested structured response."""


def _incomplete_response(payload: dict[str, Any]) -> bool:
    details = payload.get("incomplete_details")
    return payload.get("status") == "incomplete" or (
        isinstance(details, dict) and bool(details.get("reason"))
    )


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks)


def call_structured_responses_api(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 1200,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for rewrite suggestions.")

    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_output_tokens": max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
            },
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI request failed: {error.code} {body[:400]}"
        ) from error

    if _incomplete_response(parsed):
        details = parsed.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else "unknown"
        raise ResponseTruncationError(
            "OpenAI structured response was incomplete "
            f"(reason: {reason}). Increase max_output_tokens and retry; "
            "no partial JSON was returned."
        )

    text = extract_response_text(parsed)
    if not text:
        raise RuntimeError("OpenAI request returned no text.")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI request did not return JSON.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("OpenAI request did not return a JSON object.")
    return result
