import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Source
from app.repositories.sources import create_source
from app.repositories.tasks import create_task

SEED_FILE = Path(__file__).resolve().parents[2] / "data" / "seed_sources.json"


def _cron_from_hhmm(hhmm: str) -> str:
    hour, minute = hhmm.split(":")
    return f"{minute} {hour} * * *"


def seed_defaults(db: Session, settings: Settings | None = None) -> bool:
    """空库时写入内置源与默认任务；返回是否执行了种子写入。"""
    if db.query(Source).first():
        return False
    settings = settings or Settings(_env_file=None)
    with SEED_FILE.open(encoding="utf-8") as fh:
        seeds = json.load(fh)
    for item in seeds:
        create_source(
            db,
            name=item["name"],
            url=item["url"],
            feed_type=item.get("feed_type", "rss"),
            lang=item.get("lang", "en"),
            categories=item["categories"],
        )
    create_task(db, name="采集·全板块", kind="collect", category=None, cron=settings.collect_cron)
    create_task(
        db,
        name="每日分析·四板块",
        kind="analyze",
        category=None,
        cron=_cron_from_hhmm(settings.daily_analysis_hhmm),
    )
    db.commit()
    return True
