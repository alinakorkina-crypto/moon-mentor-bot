"""One Gemini request returning two Reading Engine v4.5 variants."""

from google import genai
from google.genai import types

from reading_engine_v45 import V45_RESPONSE_SCHEMA, V45_SYSTEM_INSTRUCTION


MODEL_NAME = "gemini-3.5-flash"
GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=V45_SYSTEM_INSTRUCTION,
    temperature=0.45,
    top_p=0.9,
    candidate_count=1,
    seed=42,
    max_output_tokens=2200,
    response_mime_type="application/json",
    response_schema=V45_RESPONSE_SCHEMA,
)
client = genai.Client(vertexai=True, project="moon-mentor", location="global")


def ask_gemini_v45(prompt: str) -> str | None:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME, contents=prompt, config=GENERATION_CONFIG
        )
        return response.text
    except Exception as error:
        print(f"Gemini v4.5 error: {error}")
        return None
