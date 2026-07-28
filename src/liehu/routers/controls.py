"""控制端 (线) 路由: 分时采样时间线。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..db import get_connection, rows_to_list

router = APIRouter(tags=["controls"])


@router.get("/controls")
def list_control_samples(
    control_api: str | None = Query(None, description="按控制接口过滤"),
    limit: int = Query(200, le=1000),
) -> dict:
    """列出控制接口分时采样 (时间线)。"""
    where, params = "", []
    if control_api:
        where = "WHERE control_api = ?"
        params.append(control_api)
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM control_samples {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "items": rows_to_list(rows)}


@router.get("/controls/timeline")
def control_timeline(
    start: str | None = Query(None, description="起始时间 (含), 格式 YYYY-MM-DDTHH:MM"),
    end: str | None = Query(None, description="结束时间 (含), 格式 YYYY-MM-DDTHH:MM"),
) -> dict:
    """按控制接口聚合的采样时间线 (供前端画 download_link 变化)。

    可选 ``start`` / ``end`` 按 ``observed_at`` 做时间范围筛选。observed_at 为
    定宽 ISO 时间 (YYYY-MM-DDTHH:MM:SS+08:00), 取前 16 字符 (精确到分钟) 与
    前端 ``datetime-local`` 输入按字典序比较即等价于按时间先后比较。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT control_api, observed_at, download_link, http_status, error "
            "FROM control_samples ORDER BY observed_at ASC"
        ).fetchall()
    finally:
        conn.close()

    start_key = start[:16] if start else None
    end_key = end[:16] if end else None

    timeline: dict[str, list] = {}
    for r in rows:
        key = (r["observed_at"] or "")[:16]
        if start_key and key < start_key:
            continue
        if end_key and key > end_key:
            continue
        timeline.setdefault(r["control_api"], []).append({
            "observed_at": r["observed_at"],
            "download_link": r["download_link"],
            "http_status": r["http_status"],
            "error": r["error"],
        })
    return {"timeline": timeline, "start": start, "end": end}
