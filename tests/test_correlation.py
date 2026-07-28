"""关联分析单元测试 (对应文章第二节: 多时钟分类 + 连接件归因)。"""

from __future__ import annotations

from liehu.analysis.correlation import (
    attribute_campaign,
    build_links,
    classify_registration,
    confidence,
    detect_adjacent_registration,
    detect_control_succession,
    detect_download_pool,
    detect_route_topology,
    normalize_download,
)
from liehu.models import Campaign, DayClass


def test_same_day_registration():
    """当天注册且当天公开 -> same_day (现做现用)。"""
    assert classify_registration(
        "2026-07-23T10:00:00", "2026-07-23T10:05:00"
    ) == DayClass.SAME_DAY


def test_preexisting_registration():
    """注册早于基线, 当天才被查询命中 -> preexisting (提前备货)。"""
    assert classify_registration(
        "2026-07-10T00:00:00", "2026-07-23T10:00:00"
    ) == DayClass.PREEXISTING


def test_reactivated_registration():
    """公开扫描早于本次注册 -> reactivated (历史域名重新注册)。"""
    assert classify_registration(
        "2026-07-23T00:00:00", "2025-01-01T00:00:00"
    ) == "reactivated"


def test_attribute_campaign_by_control_api():
    assert attribute_campaign("noah-admin.site/api.php") == Campaign.NOAH
    assert attribute_campaign("fezhx.com/api.php") == Campaign.FEZHX
    assert attribute_campaign("unknown.site/api.php") == Campaign.UNKNOWN
    assert attribute_campaign(None) == Campaign.UNKNOWN


def test_confidence_confirmed_on_control_api():
    """命中精确控制接口即确认 (最强连接件)。"""
    level, score = confidence({"control_api": True})
    assert level == "confirmed"
    assert score == 5


def test_confidence_candidate_on_shared_ip_only():
    """仅共享 IP -> 候选, 不进入关联集合。"""
    level, score = confidence({"shared_ip": True})
    assert level == "candidate"
    assert score == 1


def test_confidence_confirmed_on_analytics_plus_adjacent():
    level, _ = confidence({"analytics_id": True, "adjacent_reg": True})
    assert level == "confirmed"


def test_confidence_confirmed_on_shared_cert():
    """共享多-SAN 证书为强连接件, 单独即可确认 (介于 control_api 与 analytics_id)。"""
    level, score = confidence({"shared_cert": True})
    assert level == "confirmed"
    assert score == 4


def test_detect_control_succession_on_identical_response():
    """held 旧控制域与 active 新控制域响应体逐字节相同 -> 接管关系。"""
    samples = [
        {"control_domain": "page-admin.site", "resp_sha256": "SAME-HASH", "status": "held"},
        {"control_domain": "fezhx.com", "resp_sha256": "SAME-HASH", "status": "active"},
        {"control_domain": "other.site", "resp_sha256": "DIFF-HASH", "status": "active"},
    ]
    events = detect_control_succession(samples)
    assert len(events) == 1
    assert events[0]["successor"] == "fezhx.com"
    assert events[0]["predecessor"] == "page-admin.site"


def test_detect_download_pool_by_shared_cert():
    """共享同一张多-SAN 证书的下载域聚为一个供包池。"""
    records = [
        {"domain": "gehie246.com", "cert_san": "POOL-SAN"},
        {"domain": "gnrrn2821.com", "cert_san": "POOL-SAN"},
        {"domain": "lonely.com", "cert_san": "OTHER-SAN"},
    ]
    pools = detect_download_pool(records)
    assert len(pools) == 1
    assert set(pools[0]) == {"gehie246.com", "gnrrn2821.com"}


def test_detect_download_pool_by_adjacent_registration_and_ip():
    """无证书时, 同秒注册 + 同一下载宿主 IP 也聚为一池。"""
    records = [
        {"domain": "a.com", "registered_at": "2026-07-20T10:00:00", "download_ip": "67.230.179.117"},
        {"domain": "b.com", "registered_at": "2026-07-20T10:00:03", "download_ip": "67.230.179.117"},
    ]
    pools = detect_download_pool(records, window_seconds=5)
    assert len(pools) == 1
    assert set(pools[0]) == {"a.com", "b.com"}


def test_detect_adjacent_registration_groups_burst():
    """Apple Music 四站在极短时间内注册 -> 同一秒级批处理分组。"""
    records = [
        {"domain": "a.com", "registered_at": "2026-07-23T10:00:00"},
        {"domain": "b.com", "registered_at": "2026-07-23T10:00:05"},
        {"domain": "c.com", "registered_at": "2026-07-23T10:00:09"},
        {"domain": "far.com", "registered_at": "2026-07-23T12:00:00"},
    ]
    groups = detect_adjacent_registration(records, window_seconds=10)
    assert len(groups) == 1
    assert set(groups[0]) == {"a.com", "b.com", "c.com"}


def test_detect_route_merge():
    """7·22 两条控制线各自 download_link -> 7·23 合流到同一 gnrrn 路径。"""
    samples_by_round = [
        [
            {"control_api": "noah-admin.site/api.php", "download_link": "old-noah/22setup"},
            {"control_api": "fezhx.com/api.php", "download_link": "old-fezhx/setup"},
        ],
        [
            {"control_api": "noah-admin.site/api.php", "download_link": "www.gnrrn2821.com/22setup"},
            {"control_api": "fezhx.com/api.php", "download_link": "www.gnrrn2821.com/22setup"},
        ],
    ]
    events = detect_route_topology(samples_by_round)
    assert len(events) == 1
    assert events[0]["type"] == "ROUTE_MERGE"
    assert events[0]["download_link"] == "www.gnrrn2821.com/22setup"


def test_normalize_download_strips_scheme():
    """下载路径归一化: 去协议前缀与末尾斜杠, 空值原样返回。"""
    assert normalize_download("https://360down.net/x.zip") == "360down.net/x.zip"
    assert normalize_download("HTTP://360down.net/x.zip") == "360down.net/x.zip"
    assert normalize_download("360down.net/x.zip") == "360down.net/x.zip"
    assert normalize_download("www.gnrrn2821.com/22setup/") == "www.gnrrn2821.com/22setup"
    assert normalize_download(None) is None
    assert normalize_download("") == ""


def test_build_links_normalizes_download_nodes():
    """live 采样返回完整 URL 时, 图中下载路径节点应与 mock 形式一致 (不分裂)。"""
    links = build_links(
        [],
        [
            {"control_api": "noah-admin.site/api.php",
             "download_link": "https://360down.net/Install.zip"},
            {"control_api": "fezhx.com/api.php",
             "download_link": "360down.net/Install.zip"},
        ],
        [],
    )
    downloads = {lk["dst"] for lk in links if lk["dst_type"] == "download"}
    assert downloads == {"360down.net/Install.zip"}
