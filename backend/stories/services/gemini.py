
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

# Locate our reusable summarization prompt
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "summarize.md"


# Define the expected Gemini response structure
class GeneratedStory(BaseModel):
    headline: str
    summary: str


def generate_story(articles: list[str]) -> dict:
    # Load the prompt
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    # Label each article so Gemini can distinguish sources
    article_text = "\n\n".join(
        f"Article {i}:\n{article}"
        for i, article in enumerate(articles, start=1)
    )

    # Combine the instructions and articles
    full_prompt = f"{prompt}\n\nUse these articles:\n\n{article_text}"

    # Send the request to Gemini
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeneratedStory,
        ),
    )

    # Validate and return the generated story
    if not isinstance(response.parsed, GeneratedStory):
        raise ValueError("Gemini returned an invalid story response.")

    return response.parsed.model_dump()
