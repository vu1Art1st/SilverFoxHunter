"""差异事件路由: 事件流 + 差异卡 + 错误账本。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..alerting import build_diff_card
from ..db import get_connection, rows_to_list

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(
    priority: str | None = Query(None, description="按优先级过滤: high/pending/watch"),
    event_type: str | None = Query(None, description="按事件类型过滤"),
    limit: int = Query(200, le=1000),
) -> dict:
    """列出差异事件 (只推变化), 并渲染为差异卡。"""
    clauses, params = [], []
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()

    cards = [build_diff_card(dict(r)) for r in rows]
    return {"count": len(cards), "items": cards}


@router.get("/errors")
def list_errors(limit: int = 200) -> dict:
    """列出采集错误账本 (errors.jsonl 的 DB 版本)。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "items": rows_to_list(rows)}
