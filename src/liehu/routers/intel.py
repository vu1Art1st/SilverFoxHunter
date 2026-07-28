"""情报库路由: 16 篇手记时间线 + 全量 IOC 目录 + 优先级/处置/战役/状态概览。

对应新增的 intel_reports / iocs 两张情报表。所有读接口直接查询 SQLite。
confidence_json / source_anchors_json 在返回前解析为结构化对象, 便于前端渲染
置信边界表与外部归因锚点链接。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from ..db import get_connection, rows_to_list

router = APIRouter(tags=["intel"])


def _parse_json(value: str | None, default):
    """安全解析 JSON 字段, 失败时返回默认值。"""
    if not value:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


@router.get("/intel/reports")
def list_reports() -> dict:
    """返回 16 篇情报手记时间线 (按发布时间升序), 展开置信边界与外部锚点。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM intel_reports ORDER BY published_at ASC"
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows_to_list(rows):
        row["confidence"] = _parse_json(row.pop("confidence_json", None), {})
        row["source_anchors"] = _parse_json(row.pop("source_anchors_json", None), [])
        items.append(row)
    return {"count": len(items), "items": items}


@router.get("/intel/iocs")
def list_iocs(
    ioc_type: str | None = Query(None, description="按类型过滤: domain/url/ip/sha256/imphash/analytics_id/cert_san/download_path/control_api"),
    priority_tier: str | None = Query(None, description="按优先级过滤: P1/P2/P3"),
    disposition: str | None = Query(None, description="按处置过滤: block/correlate_only"),
    campaign: str | None = Query(None, description="按战役过滤: noah/fezhx/page/unknown"),
    status: str | None = Query(None, description="按状态过滤: active/held/nxdomain/unknown"),
    limit: int = Query(500, le=2000),
) -> dict:
    """列出归一化 IOC 目录, 支持按类型/优先级/处置/战役/状态过滤。"""
    clauses, params = [], []
    for field, val in (
        ("ioc_type", ioc_type),
        ("priority_tier", priority_tier),
        ("disposition", disposition),
        ("campaign", campaign),
        ("status", status),
    ):
        if val:
            clauses.append(f"{field} = ?")
            params.append(val)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM iocs {where} "
            "ORDER BY priority_tier ASC, first_report_date ASC LIMIT ?",
            (*params, limit),
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "items": rows_to_list(rows)}


@router.get("/intel/stats")
def intel_stats() -> dict:
    """按优先级/处置/战役/状态/类型分组的 IOC 计数 + 报告总数 (供概览卡)。"""
    conn = get_connection()
    try:
        report_total = conn.execute(
            "SELECT COUNT(*) AS c FROM intel_reports"
        ).fetchone()["c"]
        ioc_total = conn.execute("SELECT COUNT(*) AS c FROM iocs").fetchone()["c"]

        def group_by(column: str) -> dict:
            return {
                row[column]: row["c"]
                for row in conn.execute(
                    f"SELECT {column}, COUNT(*) AS c FROM iocs GROUP BY {column}"
                ).fetchall()
            }

        by_priority = group_by("priority_tier")
        by_disposition = group_by("disposition")
        by_campaign = group_by("campaign")
        by_status = group_by("status")
        by_type = group_by("ioc_type")
    finally:
        conn.close()

    return {
        "report_total": report_total,
        "ioc_total": ioc_total,
        "by_priority": by_priority,
        "by_disposition": by_disposition,
        "by_campaign": by_campaign,
        "by_status": by_status,
        "by_type": by_type,
    }
