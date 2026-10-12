from app.core.constants import ALL_CATEGORIES
from app.services.reports.specs import REPORT_SPECS, spec_for


def test_all_categories_have_spec():
    assert set(REPORT_SPECS) == set(ALL_CATEGORIES)


def test_daily_titles_are_category_specific():
    titles = {spec_for(c).daily_title for c in ALL_CATEGORIES}
    assert titles == {"政治每日综述", "军事态势简报", "宏观与政策简报", "市场复盘"}


def test_sections_are_distinct_between_categories():
    seen = [tuple(spec_for(c).daily_sections) for c in ALL_CATEGORIES]
    assert len(set(seen)) == len(seen)
    assert spec_for("military").daily_sections[1] == "新武器与装备动态"
    assert spec_for("economy").daily_sections[0] == "数据要点"
    assert spec_for("finance").daily_sections[0] == "资产表现"


def test_structured_blocks_match_board_features():
    assert spec_for("politics").structured_blocks == ("timeline", "stances")
    assert spec_for("military").structured_blocks == ("weapons", "timeline")
    assert spec_for("economy").structured_blocks == ("indicators", "timeline")
    assert spec_for("finance").structured_blocks == ("snapshots", "timeline")


def test_unknown_category_raises():
    import pytest

    with pytest.raises(KeyError):
        spec_for("sports")
