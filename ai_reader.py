"""Single-call OpenAI transport for plain-text Moon responses."""

from __future__ import annotations

import json
import os
import re
import subprocess

import httpx
from openai import OpenAI


MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")


def _output_text(response) -> str | None:
    text = getattr(response, "output_text", None)
    if text:
        return text.strip()
    if isinstance(response, dict):
        text = response.get("output_text") or "".join(
            item.get("text", "")
            for output in response.get("output", [])
            if output.get("type") == "message"
            for item in output.get("content", [])
            if item.get("type") == "output_text"
        )
        return text.strip() or None
    return None


def _ask_curl(prompt: str) -> str | None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or re.fullmatch(r"__SECRET[\s\S]*__", key):
        raise ValueError("Invalid OPENAI_API_KEY")
    request = {
        "model": MODEL_NAME,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 900,
        "input": prompt,
    }
    header_read, header_write = os.pipe()
    try:
        os.write(header_write, ("Authorization: Bearer " + key + "\n").encode())
        os.close(header_write)
        header_write = None
        completed = subprocess.run(
            ["curl", "--disable", "--silent", "--show-error", "--retry", "0",
             "--no-location", "--max-redirs", "0", "--connect-timeout", "15",
             "--max-time", "60", "--proto", "=https", "--request", "POST",
             "--header", f"@/dev/fd/{header_read}",
             "--header", "Content-Type: application/json", "--data-binary", "@-",
             "--write-out", "\n%{http_code}",
             "https://api.openai.com/v1/responses"],
            input=json.dumps(request, ensure_ascii=False), text=True,
            capture_output=True, pass_fds=(header_read,), timeout=65,
        )
    finally:
        os.close(header_read)
        if header_write is not None:
            os.close(header_write)
    if completed.returncode:
        raise RuntimeError(f"curl failed with exit code {completed.returncode}")
    body, separator, status = completed.stdout.rpartition("\n")
    if not separator or not re.fullmatch(r"\d{3}", status):
        raise ValueError("Invalid curl HTTP status")
    response = json.loads(body)
    if not 200 <= int(status) < 300 or response.get("error"):
        raise RuntimeError(f"OpenAI HTTP {status}")
    return _output_text(response)


def ask_openai(prompt: str) -> str | None:
    """Return one plain-text answer from exactly one OpenAI API call."""
    try:
        if os.getenv("OPENAI_TRANSPORT") == "curl":
            return _ask_curl(prompt)
        with httpx.Client(trust_env=True, follow_redirects=False, timeout=60.0) as http_client, \
                OpenAI(max_retries=0, http_client=http_client) as client:
            response = client.responses.create(
                model=MODEL_NAME,
                reasoning={"effort": "low"},
                max_output_tokens=900,
                input=prompt,
            )
        return _output_text(response)
    except Exception as error:
        print(f"OpenAI error: {type(error).__name__}")
        return None
