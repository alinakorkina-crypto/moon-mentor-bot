"""Two-pass Gemini caller for Reading Engine v7."""

from typing import Any

from google import genai
from google.genai import types

from reading_engine_v7 import (
    ANALYSIS_SCHEMA_V7,
    ANALYSIS_SYSTEM_V7,
    EDITOR_SCHEMA_V7,
    EDITOR_SYSTEM_V7,
)


MODEL_NAME = "gemini-3.5-flash"

ANALYSIS_CONFIG = types.GenerateContentConfig(
    system_instruction=ANALYSIS_SYSTEM_V7,
    thinking_config=types.ThinkingConfig(thinking_level="low"),
    temperature=0.25,
    max_output_tokens=4096,
    response_mime_type="application/json",
    response_schema=ANALYSIS_SCHEMA_V7,
)

EDITOR_CONFIG = types.GenerateContentConfig(
    system_instruction=EDITOR_SYSTEM_V7,
    thinking_config=types.ThinkingConfig(thinking_level="low"),
    temperature=0.65,
    max_output_tokens=4096,
    response_mime_type="application/json",
    response_schema=EDITOR_SCHEMA_V7,
)

client = genai.Client(vertexai=True, project="moon-mentor", location="global")


def _enum_text(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    return name if isinstance(name, str) else str(value)


def _result(response: Any) -> dict[str, Any]:
    candidates = getattr(response, "candidates", None) or []
    reason = _enum_text(getattr(candidates[0], "finish_reason", None)) if candidates else None
    usage = getattr(response, "usage_metadata", None)
    usage_dict = None
    if usage is not None:
        usage_dict = {
            field: getattr(usage, field, None)
            for field in (
                "prompt_token_count",
                "candidates_token_count",
                "thoughts_token_count",
                "total_token_count",
            )
            if getattr(usage, field, None) is not None
        }
    return {
        "text": getattr(response, "text", None),
        "finish_reason": reason,
        "usage": usage_dict,
    }


def ask_gemini_analysis_v7(prompt: str) -> dict[str, Any]:
    try:
        return _result(
            client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=ANALYSIS_CONFIG,
            )
        )
    except Exception as error:
        print(f"Gemini v7 analysis error: {error}")
        return {"text": None, "finish_reason": "ERROR", "usage": None}


def ask_gemini_editor_v7(prompt: str) -> dict[str, Any]:
    try:
        return _result(
            client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=EDITOR_CONFIG,
            )
        )
    except Exception as error:
        print(f"Gemini v7 editor error: {error}")
        return {"text": None, "finish_reason": "ERROR", "usage": None}

