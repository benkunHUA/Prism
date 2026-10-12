#!/usr/bin/env python
"""查东方财富 secid：搜关键词 → 回验报价 → 直接给出可粘贴的 MARKET_SYMBOLS 片段。

用法（在 backend 目录下执行）：

    uv run python scripts/find_secid.py 原油
    uv run python scripts/find_secid.py 黄金 白银 --class commodity --count 5
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.market_search import resolve, to_spec  # noqa: E402


def _width(text: str) -> int:
    """按终端显示宽度算长度（中日韩字符占两格）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - _width(text), 0)


def _fmt_quote(quote: dict | None) -> str:
    if not quote:
        return "无报价"
    change = quote["change_pct"]
    suffix = "" if change is None else f" {change:+.2f}%"
    return f"{quote['price']}{suffix}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按关键词查东方财富 secid")
    parser.add_argument("keywords", nargs="+", help="要查的关键词，如 原油 黄金")
    parser.add_argument("--class", dest="asset_class", default="index",
                        help="生成配置片段用的类别（默认 index）")
    parser.add_argument("--count", type=int, default=8, help="每个关键词的候选数")
    args = parser.parse_args(argv)

    for keyword in args.keywords:
        print(f"\n== {keyword} ==")
        rows = resolve(keyword, count=args.count)
        if not rows:
            print("  没有搜到结果，换个关键词试试")
            continue
        print(f"  {_pad('secid', 14)}{_pad('名称', 24)}{_pad('类型', 10)}报价")
        for row in rows:
            print(f"  {_pad(row['secid'], 14)}{_pad(row['name'][:22], 24)}"
                  f"{_pad(row['type_name'], 10)}{_fmt_quote(row['quote'])}")
        specs = [to_spec(args.asset_class, r["name"], r["secid"]) for r in rows if r["quote"]]
        if not specs:
            print("  没有候选能取到报价，换个关键词试试")
            continue
        print(f"\n  可粘贴片段（类别={args.asset_class}，多个之间用英文逗号连接）：")
        for spec in specs:
            print(f"    {spec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
