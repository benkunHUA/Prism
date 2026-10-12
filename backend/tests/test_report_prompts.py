from datetime import datetime

from app.core.config import Settings
from app.repositories import indicators
from app.services.reports.prompts import build_brief_prompt, build_daily_prompt


class _Article:
    def __init__(self, title="A", body="body", source_name="S"):
        self.title = title
        self.summary = ""
        self.content_text = body
        self.source = type("Src", (), {"name": source_name})()
        self.fetched_at = datetime(2026, 10, 11, 8, 0)


def test_daily_prompt_lists_board_sections(db):
    settings = Settings(_env_file=None)
    prompt = build_daily_prompt(db, "military", [_Article()], settings)
    assert "军事态势简报" in prompt
    for section in ("## 态势要点", "## 新武器与装备动态", "## 冲突进展",
                    "## 演习·军贸·防务快讯", "## 态势展望", "## 资料来源"):
        assert section in prompt
    assert "[1]" in prompt


def test_daily_prompt_sections_differ_per_category(db):
    settings = Settings(_env_file=None)
    materials = [_Article()]
    politics = build_daily_prompt(db, "politics", materials, settings)
    finance = build_daily_prompt(db, "finance", materials, settings)
    assert "## 议题立场变化" in politics and "## 资产表现" not in politics
    assert "## 资产表现" in finance and "## 议题立场变化" not in finance


def test_brief_prompt_uses_board_focus(db):
    settings = Settings(_env_file=None)
    prompt = build_brief_prompt(db, "finance", [_Article()], settings)
    assert "金融" in prompt and "3~5 条" in prompt
    assert "**事件：**" in prompt and "**影响：**" in prompt and "**来源：**" in prompt
    assert "市场涨跌与驱动因素" in prompt


def test_daily_prompt_includes_structured_context_when_present(db):
    settings = Settings(_env_file=None)
    indicators.upsert_indicator(db, indicator="CPI", region="中国", period="2026-09",
                                value=0.4, unit="%", merge_key="i1")
    prompt = build_daily_prompt(db, "economy", [_Article()], settings)
    assert "### 宏观指标" in prompt and "CPI" in prompt


def test_materials_are_truncated_by_settings(db):
    settings = Settings(_env_file=None, max_analysis_input_chars=10)
    prompt = build_daily_prompt(db, "politics", [_Article(body="x" * 500)], settings)
    assert "x" * 11 not in prompt
