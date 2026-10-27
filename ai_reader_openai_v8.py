"""Single-call OpenAI transport for Reading Engine v8."""

from __future__ import annotations

import os
import re
import json
import subprocess
from typing import Any

import httpx

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

from reading_engine_v8 import MODEL_NAME_V8, SYSTEM_PROMPT_V8, FINAL_SCHEMA_V8, parse_json_v8


MODEL_NAME = os.getenv("OPENAI_MODEL", MODEL_NAME_V8)


def _safe_error_message(message: str) -> str:
    """Keep useful exception details without exposing credentials."""
    message = re.sub(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^\s/<>]*@",
                     r"\1[REDACTED]@", message)
    message = re.sub(r"(?i)\bBearer\s+[^\s\"'<>]+",
                     "Bearer [REDACTED]", message)
    message = re.sub(r"\bsk-[\w.-]+", "[REDACTED]", message)
    return re.sub(r"__SECRET[^\s]*?__", "[REDACTED]", message)


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


def _ask_curl(prompt: str) -> dict[str, Any]:
    request = {
        "model": MODEL_NAME,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 900,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT_V8},
            {"role": "user", "content": prompt},
        ],
        "text": {"format": {"type": "json_schema", "name": "reading_v8",
                            "strict": True, "schema": FINAL_SCHEMA_V8}},
    }
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or re.fullmatch(r"__SECRET[\s\S]*__", key):
        raise ValueError("Invalid OPENAI_API_KEY")
    # Anonymous pipe: authorization is never placed in argv or a disk file.
    header_read, header_write = os.pipe()
    try:
        os.write(header_write, ("Authorization: Bearer " + key + "\n").encode())
        os.close(header_write)
        header_write = None
        completed = subprocess.run(
            ["curl", "--disable", "--silent", "--show-error",
             "--retry", "0", "--no-location", "--max-redirs", "0",
             "--connect-timeout", "15", "--max-time", "60",
             "--proto", "=https", "--request", "POST",
             "--header", f"@/dev/fd/{header_read}",
             "--header", "Content-Type: application/json",
             "--data-binary", "@-", "--write-out", "\n%{http_code}",
             "https://api.openai.com/v1/responses"],
            input=json.dumps(request, ensure_ascii=False),
            text=True, capture_output=True, pass_fds=(header_read,), timeout=65,
        )
    finally:
        os.close(header_read)
        if header_write is not None:
            os.close(header_write)
    if completed.returncode:
        # curl stderr can contain credentials or proxy details; do not retain it.
        raise RuntimeError(f"curl failed with exit code {completed.returncode}")
    body, separator, http_status = completed.stdout.rpartition("\n")
    if not separator or not re.fullmatch(r"\d{3}", http_status):
        raise ValueError("Invalid curl HTTP status")
    try:
        response = json.loads(body)
    except ValueError:
        raise ValueError(f"HTTP {http_status}: invalid JSON response") from None
    if not isinstance(response, dict):
        raise ValueError(f"HTTP {http_status}: response is not an object")
    raw = response.get("output_text")
    if raw is None:
        raw = "".join(
            item.get("text", "")
            for output in response.get("output", [])
            if output.get("type") == "message"
            for item in output.get("content", [])
            if item.get("type") == "output_text"
        )
    error = response.get("error")
    if not 200 <= int(http_status) < 300 or error:
        error = error if isinstance(error, dict) else {}
        message = f"HTTP {http_status}: {error.get('message') or 'Request failed'}"
        return {
            "payload": None, "raw_response_text": raw,
            "status": "ERROR", "model": response.get("model", MODEL_NAME),
            "usage": _usage(response),
            "error_type": _safe_error_message(str(error.get("type") or
                                                  error.get("code") or "CurlHTTPError")
                                               .replace(key, "[REDACTED]")),
            "error_message": _safe_error_message(message.replace(key, "[REDACTED]")),
        }
    response["output_text"] = raw
    return _parse_response(response)


def _parse_response(response: Any) -> dict[str, Any]:
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


def ask_openai_v8(prompt: str) -> dict[str, Any]:
    """Return parsed payload plus token diagnostics from exactly one API call."""
    try:
        if os.getenv("OPENAI_TRANSPORT") == "curl":
            return _ask_curl(prompt)
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
        return _parse_response(response)
    except Exception as error:
        error_message = str(error)
        if os.getenv("OPENAI_TRANSPORT") == "curl":
            key = os.environ.get("OPENAI_API_KEY", "")
            for secret in (key, key.strip()):
                if secret:
                    error_message = error_message.replace(secret, "[REDACTED]")
        error_message = _safe_error_message(error_message)
        return {
            "payload": None,
            "raw_response_text": None,
            "status": "ERROR",
            "error_type": type(error).__name__,
            "error_message": error_message,
            "model": MODEL_NAME,
            "usage": None,
        }

