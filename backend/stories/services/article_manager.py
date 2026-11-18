import hashlib
from stories.models import Article
from django.utils import timezone


def hash_article(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_existing_article(text: str):
    article_hash = hash_article(text)
    return Article.objects.filter(hash=article_hash).first()


def get_or_create_article(title: str, link: str, text: str, publisher):
    # Check whether the article already exists
    existing_article = find_existing_article(text)

    if existing_article:
        return existing_article

    # Create a new Article record
    return Article.objects.create(
        title=title,
        link=link,
        hash=hash_article(text),
        publisherid=publisher,
        dateaccessed=timezone.now(),
    )