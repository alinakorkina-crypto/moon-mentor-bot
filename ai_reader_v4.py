"""Isolated Gemini JSON caller for Reading Engine v4 previews."""

from google import genai
from google.genai import types

from reading_engine_v4 import V4_RESPONSE_SCHEMA, V4_SYSTEM_INSTRUCTION


MODEL_NAME = "gemini-3.5-flash"
GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=V4_SYSTEM_INSTRUCTION,
    temperature=0.2,
    top_p=0.8,
    candidate_count=1,
    seed=42,
    max_output_tokens=1024,
    response_mime_type="application/json",
    response_schema=V4_RESPONSE_SCHEMA,
)

client = genai.Client(
    vertexai=True,
    project="moon-mentor",
    location="global",
)


def ask_gemini_v4(prompt: str) -> str | None:
    """Make exactly one configured JSON request for Reading Engine v4."""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=GENERATION_CONFIG,
        )
        return response.text
    except Exception as error:
        print(f"Gemini v4 error: {error}")
        return None
