"""前台 (壳) 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..db import get_connection, rows_to_list

router = APIRouter(tags=["frontends"])


@router.get("/frontends")
def list_frontends(
    campaign: str | None = Query(None, description="按战役过滤: noah/fezhx"),
    day_class: str | None = Query(None, description="按当天分类过滤"),
    theme: str | None = Query(None, description="按题材过滤"),
    limit: int = Query(200, le=1000),
) -> dict:
    """列出前台状态卡, 支持按战役/当天分类/题材过滤。"""
    clauses, params = [], []
    if campaign:
        clauses.append("campaign = ?")
        params.append(campaign)
    if day_class:
        clauses.append("day_class = ?")
        params.append(day_class)
    if theme:
        clauses.append("theme = ?")
        params.append(theme)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM frontends {where} ORDER BY last_seen DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "items": rows_to_list(rows)}


@router.get("/frontends/{domain}")
def get_frontend(domain: str) -> dict:
    """获取单个前台的状态卡。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM frontends WHERE domain = ?", (domain,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else {}
