from app.models.entities import Category

ALL_CATEGORIES = [c.value for c in Category]

TIMELINE_SUBTYPES = {
    "politics": ["选举/组阁", "立法与投票", "外交与峰会", "制裁与出口管制", "条约与协议", "安全战略声明"],
    "military": ["冲突进展", "停火与和谈", "军事行动", "袭击与损失"],
    "economy": ["货币政策", "财政政策", "贸易政策", "产业政策", "监管与改革"],
    "finance": ["市场异动", "融资/IPO/并购", "监管动态", "公司重大事件", "资金与流动性"],
}
WEAPON_LIFECYCLE = ["研发", "测试", "列装", "部署", "出口", "退役"]
STANCE_TOPICS = ["对华", "俄乌", "中东", "台海", "贸易", "科技管制", "气候", "能源"]
STANCE_TONES = ["趋严", "缓和", "支持", "反对", "中性", "未定"]
IMPORTANCE_LEVELS = ["high", "medium", "low"]
