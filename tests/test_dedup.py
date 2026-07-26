"""去重/归一化单元测试 (对应文章: task.uuid 去重 + 记录数 vs 站点数)。"""

from __future__ import annotations

from liehu.analysis.dedup import (
    aggregate_by_domain,
    counts,
    dedup_by_uuid,
    normalize_domain,
)
from liehu.models import FrontendRecord


def test_normalize_domain_strips_www_and_case():
    assert normalize_domain("WWW.Example.COM.") == "example.com"
    assert normalize_domain("  Noah-Admin.Site  ") == "noah-admin.site"


def test_dedup_by_uuid_keeps_first():
    recs = [
        FrontendRecord(domain="a.com", task_uuid="u1"),
        FrontendRecord(domain="a.com", task_uuid="u1"),  # 复扫, 同 uuid
        FrontendRecord(domain="b.com", task_uuid="u2"),
    ]
    out = dedup_by_uuid(recs)
    assert len(out) == 2
    assert {r.task_uuid for r in out} == {"u1", "u2"}


def test_aggregate_by_domain_keeps_latest():
    recs = [
        FrontendRecord(domain="a.com", task_uuid="u1", last_seen="2026-07-23T10:00:00"),
        FrontendRecord(domain="www.a.com", task_uuid="u2", last_seen="2026-07-23T12:00:00"),
    ]
    agg = aggregate_by_domain(recs)
    # www.a.com 归一化为 a.com, 取 last_seen 较新者
    assert set(agg.keys()) == {"a.com"}
    assert agg["a.com"].last_seen == "2026-07-23T12:00:00"


def test_counts_records_vs_sites():
    """记录数 vs 站点数: 同站多次扫描, 记录多而站点去重。"""
    recs = [
        FrontendRecord(domain="a.com", task_uuid="u1"),
        FrontendRecord(domain="www.a.com", task_uuid="u2"),  # 同站
        FrontendRecord(domain="b.com", task_uuid="u3"),
    ]
    c = counts(recs)
    assert c["record_count"] == 3
    assert c["site_count"] == 2
