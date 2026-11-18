
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


def generate_story(
    articles: list[str],
    previous_headline: str | None = None,
    previous_summary: str | None = None,
) -> dict:
    # Load the prompt
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    # Label each article so Gemini can distinguish sources
    article_text = "\n\n".join(
        f"Article {i}:\n{article}"
        for i, article in enumerate(articles, start=1)
    )

    # Build the prompt using the current source articles.
    full_prompt = f"{prompt}\n\nCurrent source articles:\n\n{article_text}"

    # Include the previous revision as additional context when available.
    if previous_headline or previous_summary:
        previous_context = (
            f"Previous headline:\n{previous_headline or 'N/A'}\n\n"
            f"Previous summary:\n{previous_summary or 'N/A'}"
        )

        # Explain how Gemini should use the previous revision.
        full_prompt += (
            "\n\nPrevious story revision (for context only):\n"
            f"{previous_context}\n\n"
            "Use the previous revision to understand how the story has "
            "developed. Base all factual claims in the new headline and "
            "summary on the current source articles. Do not carry forward "
            "outdated or unsupported information."
        )

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
