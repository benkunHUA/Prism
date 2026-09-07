from sqlalchemy.orm import Session

from app.models.entities import Source, SourceCategory, utcnow


def list_sources(db: Session) -> list[Source]:
    return db.query(Source).order_by(Source.id).all()


def get_source(db: Session, source_id: int) -> Source | None:
    return db.get(Source, source_id)


def create_source(db: Session, *, name: str, url: str, feed_type: str,
                  lang: str, categories: list[str], enabled: bool = True) -> Source:
    source = Source(name=name, url=url, feed_type=feed_type, lang=lang, enabled=enabled)
    for cat in categories:
        source.source_categories.append(SourceCategory(category=cat))
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source: Source, *, name: str | None = None,
                  url: str | None = None, feed_type: str | None = None,
                  lang: str | None = None, enabled: bool | None = None,
                  categories: list[str] | None = None) -> Source:
    if name is not None:
        source.name = name
    if url is not None:
        source.url = url
    if feed_type is not None:
        source.feed_type = feed_type
    if lang is not None:
        source.lang = lang
    if enabled is not None:
        source.enabled = enabled
    if categories is not None:
        existing = {sc.category for sc in source.source_categories}
        for cat in set(categories) - existing:
            source.source_categories.append(SourceCategory(category=cat))
        for sc in list(source.source_categories):
            if sc.category not in categories:
                source.source_categories.remove(sc)
    db.commit()
    db.refresh(source)
    return source


def set_source_health(db: Session, source: Source, *, ok: bool,
                      error: str | None = None) -> None:
    if ok:
        source.last_ok_at = utcnow()
        source.error_count = 0
        source.last_error = None
        source.enabled = True
    else:
        source.error_count += 1
        source.last_error = error
        if source.error_count >= 3:
            source.enabled = False
    db.commit()


def delete_source(db: Session, source: Source) -> None:
    db.delete(source)
    db.commit()
