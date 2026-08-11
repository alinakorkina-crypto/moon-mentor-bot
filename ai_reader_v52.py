"""Gemini transport for v5.2 with a larger editor output budget."""

from typing import Any

from google import genai
from google.genai import types

from reading_engine_v51 import (
    ANALYSIS_SCHEMA_V51,
    ANALYSIS_SYSTEM_V51,
    EDITOR_SCHEMA_V51,
    EDITOR_SYSTEM_V51,
)


MODEL_NAME = "gemini-3.5-flash"

ANALYSIS_CONFIG = types.GenerateContentConfig(
    system_instruction=ANALYSIS_SYSTEM_V51,
    temperature=0.15,
    top_p=0.75,
    candidate_count=1,
    seed=42,
    max_output_tokens=4096,
    response_mime_type="application/json",
    response_schema=ANALYSIS_SCHEMA_V51,
)

EDITOR_CONFIG = types.GenerateContentConfig(
    system_instruction=EDITOR_SYSTEM_V51,
    temperature=0.3,
    top_p=0.85,
    candidate_count=1,
    seed=43,
    max_output_tokens=4096,
    response_mime_type="application/json",
    response_schema=EDITOR_SCHEMA_V51,
)

client = genai.Client(vertexai=True, project="moon-mentor", location="global")


def _enum_text(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    return name if isinstance(name, str) else str(value)


def _usage_dict(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    fields = (
        "prompt_token_count",
        "candidates_token_count",
        "thoughts_token_count",
        "total_token_count",
    )
    return {
        field: getattr(usage, field, None)
        for field in fields
        if getattr(usage, field, None) is not None
    }


def _response_result(response: Any) -> dict[str, Any]:
    candidates = getattr(response, "candidates", None) or []
    finish_reason = (
        _enum_text(getattr(candidates[0], "finish_reason", None))
        if candidates
        else None
    )
    return {
        "text": getattr(response, "text", None),
        "finish_reason": finish_reason,
        "usage": _usage_dict(response),
    }


def ask_gemini_analysis_v52(prompt: str) -> dict[str, Any]:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=ANALYSIS_CONFIG,
        )
        return _response_result(response)
    except Exception as error:
        print(f"Gemini v5.2 analysis error: {error}")
        return {"text": None, "finish_reason": "ERROR", "usage": None}


def ask_gemini_editor_v52(prompt: str) -> dict[str, Any]:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=EDITOR_CONFIG,
        )
        return _response_result(response)
    except Exception as error:
        print(f"Gemini v5.2 editor error: {error}")
        return {"text": None, "finish_reason": "ERROR", "usage": None}
