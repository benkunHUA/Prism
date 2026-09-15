AUTO_TIMELINE_SUBTYPES = {
    ("politics", "选举/组阁"),
    ("politics", "立法与投票"),
    ("military", "停火与和谈"),
    ("economy", "货币政策"),
    ("economy", "财政政策"),
    ("finance", "融资/IPO/并购"),
}
DECISION_WORDS = ("结果", "通过", "胜出", "宣布", "决定", "签署", "正式")
SPECIAL_WORDS = {
    ("politics", "选举/组阁"): ("结果", "胜出", "就职", "正式成立"),
    ("politics", "立法与投票"): ("通过", "否决", "表决"),
    ("military", "停火与和谈"): ("停火", "协议", "达成", "宣布"),
    ("economy", "货币政策"): ("利率", "决定", "维持", "上调", "下调"),
    ("economy", "财政政策"): ("预算", "通过", "宣布", "方案"),
    ("finance", "融资/IPO/并购"): ("收购", "合并", "IPO", "上市", "发行", "回购"),
}


def event_auto_verification(category: str, subtype: str, summary: str) -> str:
    """返回 confirmed 或 draft。"""
    if (category, subtype) not in AUTO_TIMELINE_SUBTYPES:
        return "draft"
    words = SPECIAL_WORDS.get((category, subtype), DECISION_WORDS)
    return "confirmed" if any(w in summary for w in words) else "draft"
