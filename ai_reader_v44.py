"""Gemini caller with separate v4.4 relationship and default profiles."""

from google import genai
from google.genai import types

from reading_engine_v44 import (
    V44_DEFAULT_SYSTEM_INSTRUCTION,
    V44_LOVE_SYSTEM_INSTRUCTION,
    V44_RESPONSE_SCHEMA,
)


MODEL_NAME = "gemini-3.5-flash"


def _config(system_instruction: str):
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3,
        top_p=0.85,
        candidate_count=1,
        seed=42,
        max_output_tokens=1200,
        response_mime_type="application/json",
        response_schema=V44_RESPONSE_SCHEMA,
    )


LOVE_CONFIG = _config(V44_LOVE_SYSTEM_INSTRUCTION)
DEFAULT_CONFIG = _config(V44_DEFAULT_SYSTEM_INSTRUCTION)
client = genai.Client(vertexai=True, project="moon-mentor", location="global")


def ask_gemini_v44(prompt: str) -> str | None:
    config = LOVE_CONFIG if "Тип расклада: love" in prompt else DEFAULT_CONFIG
    try:
        response = client.models.generate_content(
            model=MODEL_NAME, contents=prompt, config=config
        )
        return response.text
    except Exception as error:
        print(f"Gemini v4.4 error: {error}")
        return None
