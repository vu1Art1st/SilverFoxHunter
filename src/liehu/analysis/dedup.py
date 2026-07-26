"""去重与归一化 (对应文章"每轮原始 JSON 先落盘, 再按 task.uuid 去重")。

持续监控采用重叠时间窗 + task.uuid 去重, 以吸收索引延迟和任务抖动;
同一站点可能被复扫多次, 因此同时保留"记录数"与"站点数"两种口径。
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models import FrontendRecord


def normalize_domain(domain: str) -> str:
    """归一化 page.domain: 去空白、转小写、去末尾点、去 www. 前缀。"""
    d = (domain or "").strip().lower().rstrip(".")
    if d.startswith("www."):
        d = d[4:]
    return d


def dedup_by_uuid(records: Iterable[FrontendRecord]) -> list[FrontendRecord]:
    """按 task.uuid 去重 (保留首次出现的记录)。"""
    seen: set[str] = set()
    out: list[FrontendRecord] = []
    for rec in records:
        key = rec.task_uuid or f"{rec.domain}"
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def aggregate_by_domain(records: Iterable[FrontendRecord]) -> dict[str, FrontendRecord]:
    """按归一化 page.domain 汇总, 返回 {domain: 最新记录}。

    以 last_seen 较新者为准合并 (缺失时保留已有)。
    """
    agg: dict[str, FrontendRecord] = {}
    for rec in records:
        key = normalize_domain(rec.domain)
        rec.domain = key
        existing = agg.get(key)
        if existing is None:
            agg[key] = rec
            continue
        # 取 last_seen 较新者
        if (rec.last_seen or "") >= (existing.last_seen or ""):
            agg[key] = rec
    return agg


def counts(records: list[FrontendRecord]) -> dict[str, int]:
    """返回记录数与去重站点数 (对应文章"记录数 vs 站点数")。"""
    domains = {normalize_domain(r.domain) for r in records}
    return {"record_count": len(records), "site_count": len(domains)}
