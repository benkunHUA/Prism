from datetime import datetime

from pydantic import BaseModel, Field


class TimelineItemIn(BaseModel):
    subtype: str
    actor: str = ""
    region: str = ""
    occurred_at: datetime | None = None
    summary: str = ""
    importance: str = Field(default="medium")
    group_key: str | None = None


class WeaponItemIn(BaseModel):
    name: str = Field(min_length=1)
    original_name: str = ""
    origin: str = ""
    weapon_type: str = ""
    params_text: str = ""
    lifecycle_status: str = Field(default="研发")
    first_seen_at: datetime | None = None


class IndicatorItemIn(BaseModel):
    indicator: str
    region: str = ""
    period: str
    value: float
    unit: str = ""
    previous: float | None = None
    forecast: float | None = None
    released_at: datetime | None = None


class StanceItemIn(BaseModel):
    topic: str
    actor: str
    stance_text: str
    tone: str = "中性"
    stated_at: datetime | None = None


class PoliticsExtraction(BaseModel):
    events: list[TimelineItemIn] = []
    stances: list[StanceItemIn] = []


class MilitaryExtraction(BaseModel):
    weapons: list[WeaponItemIn] = []
    conflicts: list[TimelineItemIn] = []


class EconomyExtraction(BaseModel):
    indicators: list[IndicatorItemIn] = []
    policies: list[TimelineItemIn] = []


class FinanceExtraction(BaseModel):
    events: list[TimelineItemIn] = []


CATEGORY_MODEL = {
    "politics": PoliticsExtraction,
    "military": MilitaryExtraction,
    "economy": EconomyExtraction,
    "finance": FinanceExtraction,
}
