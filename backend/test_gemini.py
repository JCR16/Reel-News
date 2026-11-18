from stories.services.gemini import generate_story

# Example articles
articles = [
    "NASA announces a new mission to study the Moon's surface.",
    "NASA plans to launch a spacecraft to investigate lunar geology."
]

# Generate a story using our Gemini service
result = generate_story(articles)

print(result)