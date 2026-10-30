from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _blank_datetime_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


OptionalDateTime = Annotated[datetime | None, BeforeValidator(_blank_datetime_to_none)]


class TimelineItemIn(BaseModel):
    subtype: str
    actor: str = ""
    region: str = ""
    occurred_at: OptionalDateTime = None
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
    first_seen_at: OptionalDateTime = None


class IndicatorItemIn(BaseModel):
    indicator: str
    region: str = ""
    period: str
    value: float
    unit: str = ""
    previous: float | None = None
    forecast: float | None = None
    released_at: OptionalDateTime = None


class StanceItemIn(BaseModel):
    topic: str
    actor: str
    stance_text: str
    tone: str = "中性"
    stated_at: OptionalDateTime = None


class PoliticsExtraction(BaseModel):
    regions: list[str] = []
    events: list[TimelineItemIn] = []
    stances: list[StanceItemIn] = []


class MilitaryExtraction(BaseModel):
    regions: list[str] = []
    weapons: list[WeaponItemIn] = []
    conflicts: list[TimelineItemIn] = []


class EconomyExtraction(BaseModel):
    regions: list[str] = []
    indicators: list[IndicatorItemIn] = []
    policies: list[TimelineItemIn] = []


class FinanceExtraction(BaseModel):
    regions: list[str] = []
    events: list[TimelineItemIn] = []


CATEGORY_MODEL = {
    "politics": PoliticsExtraction,
    "military": MilitaryExtraction,
    "economy": EconomyExtraction,
    "finance": FinanceExtraction,
}
