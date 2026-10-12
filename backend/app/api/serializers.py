from app.models.entities import Article


def article_out(article: Article) -> dict:
    return {
        "id": article.id,
        "category": article.category,
        "title": article.title,
        "url": article.url,
        "summary": article.summary,
        "source_name": article.source.name if article.source else None,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "fetched_at": article.fetched_at.isoformat(),
        "lang": article.lang,
    }
