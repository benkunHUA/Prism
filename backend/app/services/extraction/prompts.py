from app.core.constants import STANCE_TOPICS, TIMELINE_SUBTYPES, WEAPON_LIFECYCLE


def build_extraction_prompt(category: str, *, title: str, body: str, url: str) -> str:
    allowed = "、".join(TIMELINE_SUBTYPES.get(category, []))
    extra = ""
    if category == "politics":
        extra = (
            "\nstances 数组（可空）：topic 取自 " + "、".join(STANCE_TOPICS)
            + "；actor 为表态机构；stance_text 简述立场要点；tone 取 趋严/缓和/支持/反对/中性/未定。"
        )
    elif category == "military":
        extra = (
            "\nweapons 数组（可空）：name 名称、origin 国别、weapon_type 类型"
            "（战斗机/舰艇/导弹/无人机/坦克/雷达等）、params_text 参数要点、"
            "lifecycle_status 取自 " + "、".join(WEAPON_LIFECYCLE) + "。"
        )
    elif category == "economy":
        extra = (
            "\nindicators 数组（可空）：indicator 指标名、region 地区、period 周期"
            "（如 2026-08）、value 数值、unit 单位、previous/forecast 前值与预期（可空）、"
            "released_at 发布时间。"
        )
    return (
        f"你是 {category} 板块的结构化信息提取器。仅基于给定文章，输出 JSON，不要输出其它文字。\n"
        f"events 数组（可空）：subtype 取自 {allowed}；actor 主体；region 地区；"
        "occurred_at ISO 时间；summary 事实摘要（不改写、不推断）；importance 取 high/medium/low；"
        "同一战线/同一事件多次报道时给相同 group_key。"
        + extra
        + "\n文章标题：" + title
        + "\n原文链接：" + url
        + "\n正文：\n" + (body or "")[:4000]
    )
