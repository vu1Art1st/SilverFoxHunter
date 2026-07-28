"""微步在线情报路由 (两级联动的读侧)。

    - GET /threatbook          : L1 批量打标结果全量映射 (列表页风险徽章);
    - GET /threatbook/{domain} : L2 按需详查 (弹窗触发, 24h TTL 内存缓存,
      避免反复点开弹窗重复扣配额), 同时附带 L1 落库判定作为兜底。
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException, status

from ..collectors import ThreatBookCollector
from ..config import settings
from ..db import get_connection

router = APIRouter(prefix="/threatbook", tags=["threatbook"])

# L2 详查结果缓存: domain -> (时间戳, 结果)。情报时效以天计, TTL 24h。
_DETAIL_CACHE: dict[str, tuple[float, dict]] = {}
_DETAIL_TTL_SECONDS = 24 * 3600


def _verdict_from_row(row) -> dict:
    return {
        "domain": row["domain"],
        "is_malicious": bool(row["is_malicious"]),
        "confidence_level": row["confidence_level"],
        "severity": row["severity"],
        "judgments": json.loads(row["judgments_json"] or "[]"),
        "tags": json.loads(row["tags_json"] or "[]"),
        "permalink": row["permalink"],
        "queried_at": row["queried_at"],
    }


@router.get("")
def list_verdicts() -> dict:
    """全量 L1 打标判定 (domain -> 判定), 供列表页/卡片渲染风险徽章。"""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM threatbook_verdicts").fetchall()
    finally:
        conn.close()
    verdicts = {r["domain"]: _verdict_from_row(r) for r in rows}
    return {"count": len(verdicts), "verdicts": verdicts}


@router.get("/{domain}")
def domain_detail(domain: str) -> dict:
    """L2 按需详查: 单域名完整情报上下文 (带 24h 缓存)。"""
    domain = domain.strip().lower()
    if not domain:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "域名不能为空")

    cached = _DETAIL_CACHE.get(domain)
    if cached and time.time() - cached[0] < _DETAIL_TTL_SECONDS:
        return {**cached[1], "cached": True}

    # L1 落库判定 (兜底: live 详查失败时至少返回批量打标结论)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM threatbook_verdicts WHERE domain = ?", (domain,)
        ).fetchone()
    finally:
        conn.close()
    l1_verdict = _verdict_from_row(row) if row else None

    collector = ThreatBookCollector(
        settings.threatbook.mode, settings.threatbook.api_key
    )
    try:
        detail = collector.domain_detail(domain)
    except Exception as exc:
        if l1_verdict:  # 详查失败降级为 L1 判定
            return {**l1_verdict, "source": "l1_fallback", "detail_error": str(exc), "cached": False}
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"微步详查失败: {exc}")

    result = {**detail, "l1_verdict": l1_verdict}
    _DETAIL_CACHE[domain] = (time.time(), result)
    return {**result, "cached": False}
