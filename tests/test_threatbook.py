"""微步在线 (ThreatBook) 两级联动测试: 多 KEY 轮换 / mock 判定 / L1 落库 / API。"""

from __future__ import annotations

import pytest

from liehu.collectors.threatbook import (
    QUOTA_CODES,
    ThreatBookCollector,
    ThreatBookKeyRing,
)
from liehu.config import parse_api_keys
from liehu.db import get_connection, init_db


def test_parse_api_keys_separators_and_dedup():
    """多 KEY 配置串: 逗号/分号/换行混用, 去空白去重保序。"""
    raw = "key-a, key-b;key-c\nkey-a\n  \nkey-b"
    assert parse_api_keys(raw) == ["key-a", "key-b", "key-c"]
    assert parse_api_keys(None) == []
    assert parse_api_keys("   ") == []


def test_key_ring_rotation_persists():
    """轮换索引持久化到 app_settings, 新实例从上次可用 KEY 继续。"""
    init_db()
    ring = ThreatBookKeyRing("k1,k2,k3")
    ring.index = 0
    ring._save_index()
    assert ring.ordered() == ["k1", "k2", "k3"]
    ring.commit(2)  # k1/k2 限额, 本次用 k3 成功
    assert ring.index == 2
    assert ThreatBookKeyRing("k1,k2,k3").ordered() == ["k3", "k1", "k2"]
    # 复位, 避免影响其他用例
    ring.index = 0
    ring._save_index()


def _fake_response(code: int, data: dict | None = None) -> dict:
    return {"response_code": code, "verbose_msg": "quota" if code else "ok",
            "data": data or {}}


def test_live_quota_switches_to_next_key(monkeypatch):
    """第一个 KEY 限额 -> 自动用第二个 KEY 成功, 且轮换索引前进。"""
    init_db()
    collector = ThreatBookCollector("live", "quota-key,good-key")
    collector.ring.index = 0
    used: list[str] = []

    def fake_get(url, params):
        used.append(params["apikey"])
        if params["apikey"] == "quota-key":
            return _fake_response(-4)
        return _fake_response(0, {"noah-admin.site": {
            "is_malicious": True, "confidence_level": "high", "severity": "critical",
            "judgments": ["C2"], "tags_classes": [{"tags_type": "gangs", "tags": ["银狐"]}],
            "permalink": "https://x.threatbook.com/v5/domain/noah-admin.site",
        }})

    monkeypatch.setattr(collector, "_http_get", fake_get)
    verdicts = collector.verdict_batch(["noah-admin.site"])
    assert used == ["quota-key", "good-key"]
    assert verdicts[0]["is_malicious"] is True
    assert verdicts[0]["tags"] == ["银狐"]
    # 成功 KEY 固化为当前索引, 下次调用直接从 good-key 开始
    assert collector.ring.ordered()[0] == "good-key"
    collector.ring.index = 0
    collector.ring._save_index()


def test_live_all_keys_exhausted_raises(monkeypatch):
    """全部 KEY 限额 -> 抛错并列出各 KEY 状态 (交上层错误账本)。"""
    collector = ThreatBookCollector("live", "k1;k2")
    monkeypatch.setattr(collector, "_http_get", lambda url, params: _fake_response(-1))
    with pytest.raises(RuntimeError, match="均已达限额"):
        collector.verdict_batch(["fezhx.com"])


def test_live_without_keys_raises():
    collector = ThreatBookCollector("live", None)
    with pytest.raises(RuntimeError, match="未配置 API KEY"):
        collector.verdict_batch(["fezhx.com"])


def test_quota_codes_cover_documented_values():
    assert {-1, -4} <= QUOTA_CODES


def test_mock_verdicts_by_role():
    """mock 判定与复原数据集角色一致: C2/下载宿主/仿冒站点恶意, 未知域名未检出。"""
    collector = ThreatBookCollector("mock")
    by_domain = {v["domain"]: v for v in collector.verdict_batch([
        "noah-admin.site",            # C2
        "www.gnrrn2821.com",          # 下载宿主
        "apple-app.com.cn",           # 仿冒站点
        "example.com",                # 未知
    ])}
    assert by_domain["noah-admin.site"]["judgments"] == ["C2", "Trojan"]
    assert by_domain["www.gnrrn2821.com"]["judgments"] == ["Malware"]
    assert "Phishing" in by_domain["apple-app.com.cn"]["judgments"]
    assert by_domain["apple-app.com.cn"]["tags"] == ["银狐"]
    assert by_domain["example.com"]["is_malicious"] is False


def test_mock_detail_has_context():
    """mock 详查返回样本/解析 IP/whois 上下文, 与包层 IOC 可交叉印证。"""
    detail = ThreatBookCollector("mock").domain_detail("apple-app.com.cn")
    assert detail["is_malicious"] is True
    assert detail["cur_ips"][0]["ip"]
    assert detail["cur_whois"]["cdate"]
    assert detail["samples"][0]["malware_family"] == "SilverFox"


# ---- API 集成 (登录态 client 来自 conftest) -----------------------------------

def test_threatbook_requires_auth(anon_client):
    assert anon_client.get("/api/threatbook").status_code == 401


def test_threatbook_l1_batch_and_list_api(client):
    """触发一轮追踪 -> L1 批量打标落库 -> 列表接口返回徽章数据。"""
    r = client.post("/api/campaigns/trigger")
    assert r.status_code == 200
    tb = r.json()["result"]["threatbook"]
    assert tb["verdicts"] > 0
    assert tb["malicious"] > 0

    r = client.get("/api/threatbook")
    assert r.status_code == 200
    verdicts = r.json()["verdicts"]
    assert verdicts["noah-admin.site"]["is_malicious"] is True
    assert "银狐" in verdicts["apple-app.com.cn"]["tags"]
    # 下载宿主 (links 表 download 节点 host) 也被打标
    assert verdicts["www.gnrrn2821.com"]["judgments"] == ["Malware"]


def test_threatbook_l2_detail_api_with_cache(client):
    """L2 详查接口: 首次实查, 再次命中 24h 缓存。"""
    r = client.get("/api/threatbook/apple-app.com.cn")
    assert r.status_code == 200
    first = r.json()
    assert "Phishing" in first["judgments"]
    assert first["permalink"].startswith("https://x.threatbook.com/")

    r = client.get("/api/threatbook/apple-app.com.cn")
    assert r.json()["cached"] is True


def test_threatbook_verdicts_persisted_in_db(client):
    """L1 判定落库 threatbook_verdicts, INSERT OR REPLACE 保留最新。"""
    client.post("/api/campaigns/trigger")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM threatbook_verdicts WHERE domain = ?", ("fezhx.com",)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["is_malicious"] == 1
    assert "C2" in row["judgments_json"]
