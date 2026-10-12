from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportSpec:
    """单个板块的报告规范：文案、栏目、侧重与需要注入的结构化区块。"""

    category: str
    label: str
    daily_title: str
    daily_sections: tuple[str, ...]
    daily_focus: str
    brief_focus: str
    structured_blocks: tuple[str, ...]


REPORT_SPECS: dict[str, ReportSpec] = {
    "politics": ReportSpec(
        category="politics",
        label="政治",
        daily_title="政治每日综述",
        daily_sections=("今日要闻", "事件脉络", "议题立场变化", "下一步看点"),
        daily_focus=(
            "读者关心「谁在做决定、为什么、下一步会怎样」。按时间顺序梳理决定与表态，"
            "指出各方立场的变化方向，并给出可验证的下一步观察点。"
        ),
        brief_focus="聚焦当天最重要的政治决定、表态与外交动作，说明其影响对象与后续走向。",
        structured_blocks=("timeline", "stances"),
    ),
    "military": ReportSpec(
        category="military",
        label="军事",
        daily_title="军事态势简报",
        daily_sections=(
            "态势要点",
            "新武器与装备动态",
            "冲突进展",
            "演习·军贸·防务快讯",
            "态势展望",
        ),
        daily_focus=(
            "读者关心「谁有了什么新武器、仗打到哪一步」。装备条目要给出可核实的名称、国别、"
            "类型、状态与已知参数；冲突按战线分条推进，明确控制区或打击范围的变化。"
        ),
        brief_focus="聚焦新装备动态与冲突战线进展，只写有材料支撑的事实性变化。",
        structured_blocks=("weapons", "timeline"),
    ),
    "economy": ReportSpec(
        category="economy",
        label="经济",
        daily_title="宏观与政策简报",
        daily_sections=("数据要点", "政策动作与影响对象", "机构预测调整", "传导提示"),
        daily_focus=(
            "读者关心「数据说明现状、政策指明方向」。数据要点须写明数值、前值、预期与超预期/"
            "不及预期判断；政策动作写明执行机构、工具与直接影响对象。"
        ),
        brief_focus="聚焦当天的数据发布与政策动作，说明方向性含义与受影响行业。",
        structured_blocks=("indicators", "timeline"),
    ),
    "finance": ReportSpec(
        category="finance",
        label="金融",
        daily_title="市场复盘",
        daily_sections=("资产表现", "驱动事件归因", "资金与风险信号", "明日关注"),
        daily_focus=(
            "读者关心「价格怎么变、为什么变、风险在哪」。资产表现按板块与资产类别列出涨跌幅，"
            "归因只能引用材料中出现的驱动因素，风险信号要指出具体指标或事件。"
        ),
        brief_focus="聚焦主要市场涨跌与驱动因素，标明风险信号。",
        structured_blocks=("snapshots", "timeline"),
    ),
}


def spec_for(category: str) -> ReportSpec:
    spec = REPORT_SPECS.get(category)
    if spec is None:
        raise KeyError(f"未知板块: {category}")
    return spec
