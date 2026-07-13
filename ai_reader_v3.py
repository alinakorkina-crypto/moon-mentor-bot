"""Isolated deterministic Gemini caller for Reading Engine v3 previews.

This module is not imported by main.py or the working bot.
"""

from google import genai
from google.genai import types

from reading_engine_v3 import SYSTEM_INSTRUCTION_V3


MODEL_NAME = "gemini-3.5-flash"
GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION_V3,
    temperature=0.2,
    top_p=0.8,
    candidate_count=1,
    seed=42,
    max_output_tokens=512,
)

client = genai.Client(
    vertexai=True,
    project="moon-mentor",
    location="global",
)


def ask_gemini_v3(prompt: str) -> str | None:
    """Make one configured Gemini request for the isolated v3 experiment."""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=GENERATION_CONFIG,
        )
        return response.text
    except Exception as error:
        print(f"Gemini v3 error: {error}")
        return None
