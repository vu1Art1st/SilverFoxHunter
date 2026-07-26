"""载荷 (包) 路由: 结构换代对比。"""

from __future__ import annotations

from fastapi import APIRouter

from ..db import get_connection, rows_to_list

router = APIRouter(tags=["payloads"])


@router.get("/payloads")
def list_payloads(limit: int = 200) -> dict:
    """列出载荷观测记录 (按时间倒序)。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM payloads ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return {"count": len(rows), "items": rows_to_list(rows)}


@router.get("/payloads/compare")
def compare_payloads() -> dict:
    """返回按 structure_id 归组的结构对比 (供前端画换代对比表)。

    展示完整哈希轮换 (同 structure_id 多条) 与结构换代 (不同 structure_id)。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM payloads ORDER BY observed_at ASC"
        ).fetchall()
    finally:
        conn.close()

    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["structure_id"], []).append(dict(r))

    skeletons = []
    for sid, items in groups.items():
        skeletons.append({
            "structure_id": sid,
            "sample_count": len(items),
            "msi_size": items[0]["msi_size"],
            "embedded_pe_size": items[0]["embedded_pe_size"],
            "pe_entry_rva": items[0]["pe_entry_rva"],
            "stable_sha256": items[0]["stable_sha256"],
            "imphash": items[0]["imphash"],
            "ole_stream_count": items[0]["ole_stream_count"],
            "ole_identical": items[0]["ole_identical"],
            "wix_version": items[0]["wix_version"],
            "full_hashes": [i["full_sha256"] for i in items],
        })
    return {"skeletons": skeletons}
