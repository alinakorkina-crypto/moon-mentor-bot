"""Two configured Gemini calls for Reading Engine v5."""

from google import genai
from google.genai import types

from reading_engine_v5 import (
    ANALYSIS_SCHEMA_V5,
    ANALYSIS_SYSTEM_V5,
    EDITOR_SCHEMA_V5,
    EDITOR_SYSTEM_V5,
)


MODEL_NAME = "gemini-3.5-flash"

ANALYSIS_CONFIG = types.GenerateContentConfig(
    system_instruction=ANALYSIS_SYSTEM_V5,
    temperature=0.15,
    top_p=0.75,
    candidate_count=1,
    seed=42,
    max_output_tokens=1400,
    response_mime_type="application/json",
    response_schema=ANALYSIS_SCHEMA_V5,
)

EDITOR_CONFIG = types.GenerateContentConfig(
    system_instruction=EDITOR_SYSTEM_V5,
    temperature=0.3,
    top_p=0.85,
    candidate_count=1,
    seed=43,
    max_output_tokens=1000,
    response_mime_type="application/json",
    response_schema=EDITOR_SCHEMA_V5,
)

client = genai.Client(vertexai=True, project="moon-mentor", location="global")


def ask_gemini_analysis_v5(prompt: str) -> str | None:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=ANALYSIS_CONFIG,
        )
        return response.text
    except Exception as error:
        print(f"Gemini v5 analysis error: {error}")
        return None


def ask_gemini_editor_v5(prompt: str) -> str | None:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=EDITOR_CONFIG,
        )
        return response.text
    except Exception as error:
        print(f"Gemini v5 editor error: {error}")
        return None
