"""翻译提示词与文案常量。只放字符串与纯函数，不做 IO。"""

from __future__ import annotations

SUMMARY_LIMIT = 120

INSTRUCTION = (
    "把下面每条新闻的标题和摘要翻成简体中文，只做翻译与压缩，不补充原文没有的信息。\n"
    f"summary_zh 是中文要点，不超过 {SUMMARY_LIMIT} 字，不要逐字直译；原文没有摘要时给空字符串。\n"
    "严格输出 JSON 数组，不要输出其它文字，不要加代码块围栏，index 必须与输入的方括号编号一致，"
    "且每条都要出现。\n"
    '格式：[{"index": 0, "title_zh": "...", "summary_zh": "..."}]'
)


def build_translation_prompt(items: list[tuple[int, str, str]]) -> str:
    """items 为 (index, 标题, 摘要)，摘要调用方已截断。"""
    lines = [INSTRUCTION, ""]
    for index, title, summary in items:
        lines.append(f"[{index}] 标题：{title}")
        lines.append(f"[{index}] 摘要：{summary or '（无）'}")
    return "\n".join(lines)
