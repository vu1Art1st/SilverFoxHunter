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


def test_frontends_filter_by_domain_keyword(client):
    """域名关键词模糊筛选: 命中包含关键词的域名, 且可与其他过滤条件叠加。"""
    r = client.get("/api/frontends", params={"q": "apple", "limit": 1000})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all("apple" in f["domain"] for f in data["items"])

    # 与集群过滤叠加
    r = client.get("/api/frontends", params={"q": "apple", "campaign": "noah", "limit": 1000})
    assert all(
        "apple" in f["domain"] and f["campaign"] == "noah" for f in r.json()["items"]
    )

    # 无匹配关键词返回空集
    r = client.get("/api/frontends", params={"q": "no-such-domain-keyword"})
    assert r.json()["count"] == 0


def test_frontends_domain_keyword_like_escape(client):
    """LIKE 通配符应被转义: % 与 _ 作为字面量匹配, 不产生意外命中。"""
    r = client.get("/api/frontends", params={"q": "%", "limit": 1000})
    assert r.status_code == 200
    assert r.json()["count"] == 0  # 域名中不含字面 % 字符


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


def test_frontends_export_csv(client):
    """CSV 导出: UTF-8 BOM 编码 + 全量字段表头 + 数据行数与水位一致。"""
    r = client.get("/api/frontends/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    body = r.content.decode("utf-8-sig")  # BOM 存在时 utf-8-sig 可正确剥离
    assert r.content.startswith(b"\xef\xbb\xbf")  # Excel 兼容的 UTF-8 BOM
    lines = [ln for ln in body.split("\r\n") if ln]
    assert lines[0].startswith("域名,IP 地址,页面标题")
    assert len(lines) == 1 + 143  # 表头 + 143 个仿冒站点


def test_frontends_export_csv_with_filter(client):
    """CSV 导出应支持与列表页相同的过滤条件。"""
    r = client.get("/api/frontends/export.csv", params={"campaign": "fezhx"})
    assert r.status_code == 200
    lines = [ln for ln in r.content.decode("utf-8-sig").split("\r\n") if ln]
    assert len(lines) == 1 + 32  # 表头 + fezhx 集群 32 个


def test_frontend_screenshot_unknown_domain(client):
    """未入库域名的截图探测应返回 unknown, 不触发外联探测。"""
    r = client.get("/api/frontends/not-in-db.example/screenshot")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "unknown"
