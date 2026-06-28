from google import genai

client = genai.Client(
    vertexai=True,
    project="moon-mentor",
    location="global",
)

def ask_gemini(prompt: str) -> str:
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return None