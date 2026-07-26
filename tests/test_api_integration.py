"""API 集成测试: 通过 FastAPI TestClient 验证读接口与关联图端点。

说明: 应用 lifespan 会在数据库为空时自动执行种子回放并创建默认管理员, 因此本测试
无需外部准备即可运行。数据库隔离与已登录 client 夹具见 conftest.py。
"""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_stats_water_mark(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    # 复原文章 7·23 水位: 143 个前台, noah/fezhx 两个战役
    assert data["frontend_total"] == 143
    assert data["by_campaign"]["noah"] == 111
    assert data["by_campaign"]["fezhx"] == 32
    assert data["event_total"] > 0


def test_frontends_filter_by_campaign(client):
    r = client.get("/api/frontends", params={"campaign": "noah", "limit": 1000})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 111
    assert all(f["campaign"] == "noah" for f in data["items"])


def test_campaign_graph_shell_line_package(client):
    """关联图应包含壳/线/包三层节点与边。"""
    r = client.get("/api/campaigns/graph")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) > 0
    assert len(data["links"]) > 0
    node_types = {n["node_type"] for n in data["nodes"]}
    # 至少覆盖 壳(frontend) + 线(control) 两层
    assert "frontend" in node_types
    assert "control" in node_types


def test_events_priority_filter(client):
    r = client.get("/api/events", params={"priority": "high", "limit": 500})
    assert r.status_code == 200
    data = r.json()
    assert all(c["priority"] == "high" for c in data["items"])


def test_payload_compare_has_skeletons(client):
    """载荷对比应至少含两个结构骨架 (9.1MB 换代 6.9MB)。"""
    r = client.get("/api/payloads/compare")
    assert r.status_code == 200
    skeletons = r.json()["skeletons"]
    assert len(skeletons) >= 2
