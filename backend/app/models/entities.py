from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(str, enum.Enum):
    politics = "politics"
    economy = "economy"
    finance = "finance"
    military = "military"


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    feed_type: Mapped[str] = mapped_column(String(10), default="rss")
    lang: Mapped[str] = mapped_column(String(10), default="en")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source_categories: Mapped[list[SourceCategory]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    articles: Mapped[list[Article]] = relationship(back_populates="source")


class SourceCategory(Base):
    __tablename__ = "source_categories"
    __table_args__ = (UniqueConstraint("source_id", "category", name="uq_source_category"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(20))
    source: Mapped[Source] = relationship(back_populates="source_categories")


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(20), index=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    content_text: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64), index=True)
    lang: Mapped[str] = mapped_column(String(10), default="en")

    source: Mapped[Source | None] = relationship(back_populates="articles")
    analysis_links: Mapped[list[AnalysisArticle]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)  # brief | daily
    category: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    content_md: Mapped[str] = mapped_column(Text, default="")
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    model: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(10), default="success", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    article_links: Mapped[list[AnalysisArticle]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class AnalysisArticle(Base):
    __tablename__ = "analysis_articles"
    __table_args__ = (
        UniqueConstraint("analysis_id", "article_id", name="uq_analysis_article"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    analysis: Mapped[Analysis] = relationship(back_populates="article_links")
    article: Mapped[Article] = relationship(back_populates="analysis_links")


class TimelineEvent(Base):
    """四类事件共用底表：政治 / 军事冲突 / 经济政策 / 金融市场。"""
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    subtype: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(Text, default="")
    region: Mapped[str] = mapped_column(String(200), default="")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[str] = mapped_column(String(10), default="medium")
    verification_status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    group_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    merge_key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MilitaryWeapon(Base):
    __tablename__ = "military_weapons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(500), default="")
    origin: Mapped[str] = mapped_column(String(200), default="")
    weapon_type: Mapped[str] = mapped_column(String(100), default="")
    params_text: Mapped[str] = mapped_column(Text, default="")
    lifecycle_status: Mapped[str] = mapped_column(String(20), default="研发")
    merge_key: Mapped[str] = mapped_column(String(64), index=True)
    verification_status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MacroIndicator(Base):
    __tablename__ = "macro_indicators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(200), default="")
    period: Mapped[str] = mapped_column(String(50))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="")
    previous: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast: Mapped[float | None] = mapped_column(Float, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    merge_key: Mapped[str] = mapped_column(String(64), index=True)
    verification_status: Mapped[str] = mapped_column(String(10), default="confirmed", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_code: Mapped[str] = mapped_column(String(50), index=True)
    asset_name: Mapped[str] = mapped_column(String(100), default="")
    asset_class: Mapped[str] = mapped_column(String(20), default="index")
    price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(100), default="stooq")


class StanceTopic(Base):
    __tablename__ = "stance_topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(100), index=True)
    actor: Mapped[str] = mapped_column(String(200), index=True)
    stance_text: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(50), default="中性")
    stated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), index=True)  # collect | analyze
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cron: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RunLog(Base):
    __tablename__ = "run_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="running")
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class KVSetting(Base):
    __tablename__ = "kv_settings"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
