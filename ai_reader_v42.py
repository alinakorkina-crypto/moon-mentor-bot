"""Isolated Gemini caller for Reading Engine v4.2."""

from google import genai
from google.genai import types

from reading_engine_v42 import V42_RESPONSE_SCHEMA, V42_SYSTEM_INSTRUCTION


MODEL_NAME = "gemini-3.5-flash"
GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=V42_SYSTEM_INSTRUCTION,
    temperature=0.3,
    top_p=0.85,
    candidate_count=1,
    seed=42,
    max_output_tokens=1200,
    response_mime_type="application/json",
    response_schema=V42_RESPONSE_SCHEMA,
)
client = genai.Client(vertexai=True, project="moon-mentor", location="global")


def ask_gemini_v42(prompt: str) -> str | None:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME, contents=prompt, config=GENERATION_CONFIG
        )
        return response.text
    except Exception as error:
        print(f"Gemini v4.2 error: {error}")
        return None
