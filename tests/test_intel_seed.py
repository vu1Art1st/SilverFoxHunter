"""情报库入库与 API 集成测试。

验证 seed_intel 幂等回放后:
    - 16 篇情报手记全部入库 (GET /api/intel/reports);
    - IOC 目录达到下限, 且优先级/处置分级正确;
    - UPSERT 幂等 (重复 seed 不产生重复行);
    - 概览统计端点返回按维度分组的计数。

数据库隔离与已登录 client 夹具见 conftest.py。
"""

from __future__ import annotations


def test_intel_reports_count_is_16(client):
    """16 篇文章全部入库, 按发布时间升序返回, 展开置信/锚点结构。"""
    r = client.get("/api/intel/reports")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 16
    assert len(data["items"]) == 16
    # 时间线升序
    dates = [it["published_at"] for it in data["items"]]
    assert dates == sorted(dates)
    # 结构化字段已展开
    first = data["items"][0]
    assert isinstance(first["confidence"], dict)
    assert isinstance(first["source_anchors"], list)
    assert first["url"].startswith("https://mp.weixin.qq.com/s/")


def test_intel_iocs_lower_bound_and_fields(client):
    """IOC 目录达到下限, 每条含 priority_tier / disposition。"""
    r = client.get("/api/intel/iocs", params={"limit": 2000})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 40
    assert all(i["priority_tier"] in ("P1", "P2", "P3") for i in data["items"])
    assert all(i["disposition"] in ("block", "correlate_only") for i in data["items"])


def test_intel_iocs_control_api_is_p1_block(client):
    """控制接口 IOC -> P1/block。"""
    r = client.get("/api/intel/iocs", params={"ioc_type": "control_api", "limit": 2000})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(i["priority_tier"] == "P1" and i["disposition"] == "block" for i in items)


def test_intel_iocs_analytics_id_is_p3_correlate_only(client):
    """51.LA 分析ID -> P3/correlate_only (仅聚类不封禁)。"""
    r = client.get("/api/intel/iocs", params={"ioc_type": "analytics_id", "limit": 2000})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(i["priority_tier"] == "P3" and i["disposition"] == "correlate_only" for i in items)


def test_intel_iocs_filter_by_priority_and_disposition(client):
    """过滤条件生效: P1 全部 block; correlate_only 全部 P3。"""
    r = client.get("/api/intel/iocs", params={"priority_tier": "P1", "limit": 2000})
    assert all(i["priority_tier"] == "P1" for i in r.json()["items"])

    r = client.get("/api/intel/iocs", params={"disposition": "correlate_only", "limit": 2000})
    assert all(i["disposition"] == "correlate_only" for i in r.json()["items"])


def test_intel_stats_grouping(client):
    """概览统计: 报告 16 篇 + 按优先级/处置/战役/状态/类型分组计数一致。"""
    r = client.get("/api/intel/stats")
    assert r.status_code == 200
    stats = r.json()
    assert stats["report_total"] == 16
    assert stats["ioc_total"] >= 40
    # 分组计数之和应等于总数
    assert sum(stats["by_priority"].values()) == stats["ioc_total"]
    assert sum(stats["by_disposition"].values()) == stats["ioc_total"]
    assert set(stats["by_priority"]) <= {"P1", "P2", "P3"}
    assert set(stats["by_disposition"]) <= {"block", "correlate_only"}


def test_intel_events_wired_into_event_stream(client):
    """情报方法学已接入事件流: 派生出三类高优事件而非空转。"""
    for etype in ("CONTROL_TAKEOVER", "DOWNLOAD_MIGRATION", "DEAD_LINK_DELIVERY"):
        r = client.get("/api/events", params={"event_type": etype, "limit": 1000})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1, f"{etype} 未派生任何事件"
        assert all(c["event_type"] == etype for c in items)
        assert all(c["priority"] == "high" for c in items)


def test_intel_succession_and_migration_edges_in_graph(client):
    """控制面继承与下载迁移已落地关联图: 存在 succeeds 与 migrates_to 边。"""
    r = client.get("/api/campaigns/graph")
    assert r.status_code == 200
    links = r.json()["links"]
    assert any(l["relation"] == "succeeds" for l in links), "缺失控制面继承边"
    assert any(l["relation"] == "migrates_to" for l in links), "缺失下载迁移边"


def test_seed_intel_is_idempotent(client):
    """再次执行 seed_intel 不应产生重复行 (ON CONFLICT UPSERT)。"""
    from liehu.db import db_session
    from liehu.seed import seed_intel

    before_reports = client.get("/api/intel/reports").json()["count"]
    before_iocs = client.get("/api/intel/iocs", params={"limit": 2000}).json()["count"]

    with db_session() as conn:
        result = seed_intel(conn)
    assert result["reports"] == 16

    after_reports = client.get("/api/intel/reports").json()["count"]
    after_iocs = client.get("/api/intel/iocs", params={"limit": 2000}).json()["count"]
    assert after_reports == before_reports == 16
    assert after_iocs == before_iocs
