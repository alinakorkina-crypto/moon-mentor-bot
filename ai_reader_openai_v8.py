"""Single-call OpenAI transport for Reading Engine v8."""

from __future__ import annotations

import os
from typing import Any

import httpx

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from reading_engine_v8 import MODEL_NAME_V8, SYSTEM_PROMPT_V8, FINAL_SCHEMA_V8, parse_json_v8


MODEL_NAME = os.getenv("OPENAI_MODEL", MODEL_NAME_V8)


class ReadingResponseV8(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_text: str


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _usage(response: Any) -> dict[str, int] | None:
    usage = _value(response, "usage")
    if usage is None:
        return None
    input_details = _value(usage, "input_tokens_details")
    output_details = _value(usage, "output_tokens_details")
    return {
        "input_tokens": int(_value(usage, "input_tokens", 0) or 0),
        "cached_input_tokens": int(_value(input_details, "cached_tokens", 0) or 0),
        "output_tokens": int(_value(usage, "output_tokens", 0) or 0),
        "reasoning_tokens": int(_value(output_details, "reasoning_tokens", 0) or 0),
        "total_tokens": int(_value(usage, "total_tokens", 0) or 0),
    }


def ask_openai_v8(prompt: str) -> dict[str, Any]:
    """Return parsed payload plus token diagnostics from exactly one API call."""
    try:
        with httpx.Client(
            trust_env=True,
            follow_redirects=False,
            timeout=60.0,
        ) as http_client, OpenAI(max_retries=0, http_client=http_client) as client:
            response = client.responses.create(
                model=MODEL_NAME,
                reasoning={"effort": "low"},
                max_output_tokens=900,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT_V8},
                    {"role": "user", "content": prompt},
                ],
                text={"format": {"type": "json_schema", "name": "reading_v8",
                                 "strict": True, "schema": FINAL_SCHEMA_V8}},
            )
        # Preserve available response data before validating the model's JSON.
        raw = _value(response, "output_text")
        payload, issues = parse_json_v8(raw)
        if payload is not None:
            try:
                ReadingResponseV8.model_validate(payload)
            except ValidationError:
                issues.append("schema_validation_error")
        return {
            "payload": payload,
            "raw_response_text": raw,
            "status": _value(response, "status"),
            "model": _value(response, "model", MODEL_NAME),
            "usage": _usage(response),
            "issues": issues,
        }
    except Exception as error:
        return {
            "payload": None,
            "raw_response_text": None,
            "status": "ERROR",
            "error_type": type(error).__name__,
            "model": MODEL_NAME,
            "usage": None,
        }

