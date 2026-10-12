from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import indicators as indicators_repo
from app.repositories import snapshots as snapshots_repo
from app.repositories import stances as stances_repo
from app.repositories import timeline as timeline_repo
from app.repositories import weapons as weapons_repo
from app.services.reports.specs import ReportSpec

BLOCK_LIMIT = 20


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _timeline_block(db: Session, category: str) -> str:
    events = timeline_repo.list_events(
        db, category=category, verification="confirmed", limit=BLOCK_LIMIT
    )
    if not events:
        return ""
    lines = ["### 事件时间线（本系统已确认条目）"]
    for e in events:
        when = f"{e.occurred_at:%Y-%m-%d}" if e.occurred_at else "日期未定"
        lines.append(
            f"- {when} | {e.subtype} | {e.actor or '—'} | {e.region or '—'} | "
            f"[{e.importance}] {e.summary}"
        )
    return "\n".join(lines)


def _weapons_block(db: Session) -> str:
    rows = weapons_repo.list_weapons(db, verification="confirmed", limit=BLOCK_LIMIT)
    if not rows:
        return ""
    lines = ["### 武器档案（本系统已确认条目）"]
    for w in rows:
        params = (w.params_text or "").replace("\n", " / ")
        line = (
            f"- {w.name}" + (f"（{w.original_name}）" if w.original_name else "")
            + f" | {w.origin or '—'} | {w.weapon_type or '—'} | {w.lifecycle_status or '—'}"
        )
        if params:
            line += f" | 参数: {params}"
        lines.append(line)
    return "\n".join(lines)


def _stances_block(db: Session) -> str:
    rows = stances_repo.list_stances(db, verification="confirmed", limit=BLOCK_LIMIT)
    if not rows:
        return ""
    lines = ["### 议题立场（本系统已确认条目）"]
    for s in rows:
        when = f"{s.stated_at:%Y-%m-%d}" if s.stated_at else "日期未定"
        lines.append(f"- {when} | {s.topic} | {s.actor} | 基调 {s.tone} | {s.stance_text}")
    return "\n".join(lines)


def _indicators_block(db: Session) -> str:
    rows = indicators_repo.list_indicators(db, limit=BLOCK_LIMIT)
    if not rows:
        return ""
    lines = ["### 宏观指标（本系统已入库条目）"]
    for i in rows:
        parts = [f"{i.region or '—'} {i.period or '—'} {i.indicator} = {i.value}{i.unit or ''}"]
        if i.previous is not None:
            parts.append(f"前值 {i.previous}{i.unit or ''}")
        if i.forecast is not None:
            parts.append(f"预期 {i.forecast}{i.unit or ''}")
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _snapshots_block(db: Session) -> str:
    batch_ids = snapshots_repo.recent_batch_ids(db, limit=2)
    if not batch_ids:
        return ""
    latest = {s.asset_name: s for s in snapshots_repo.list_snapshots(db, batch_id=batch_ids[0])}
    previous = (
        {s.asset_name: s for s in snapshots_repo.list_snapshots(db, batch_id=batch_ids[1])}
        if len(batch_ids) > 1
        else {}
    )
    lines = [f"### 市场快照（批次 {batch_ids[0]}）"]
    for name, snap in sorted(latest.items(), key=lambda kv: kv[1].asset_class or ""):
        line = (
            f"- {snap.asset_class or '—'} | {name} | 价格 {snap.price} | "
            f"本批次 {_fmt_pct(snap.change_pct)}"
        )
        prev = previous.get(name)
        if prev is not None:
            line += f" | 上轮涨跌 {_fmt_pct(prev.change_pct)} | 上轮价格 {prev.price}"
        lines.append(line)
    return "\n".join(lines)


_BLOCK_BUILDERS = {
    "timeline": lambda db, spec: _timeline_block(db, spec.category),
    "weapons": lambda db, spec: _weapons_block(db),
    "stances": lambda db, spec: _stances_block(db),
    "indicators": lambda db, spec: _indicators_block(db),
    "snapshots": lambda db, spec: _snapshots_block(db),
}


def build_board_context(db: Session, spec: ReportSpec) -> str:
    """按板块规范装配结构化上下文；无数据时返回空字符串。"""

    blocks = [
        _BLOCK_BUILDERS[name](db, spec)
        for name in spec.structured_blocks
        if name in _BLOCK_BUILDERS
    ]
    return "\n\n".join(block for block in blocks if block)
