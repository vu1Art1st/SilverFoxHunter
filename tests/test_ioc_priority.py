"""IOC 优先级分级与处置类别 (analysis/ioc_priority.py) 单元测试。

覆盖文章第一篇的 P1/P2/P3 与"仅聚类不封禁"边界:
    - 精确控制接口 / 当前下载路径 / 仿冒前台域 -> P1 / block
    - 载荷哈希 / 专用宿主 IP -> P2 / block
    - 51.LA 分析ID / 共享证书 / Cloudflare 共享边缘 -> P3 / correlate_only
"""

from __future__ import annotations

from liehu.analysis.ioc_priority import (
    BLOCK,
    CORRELATE_ONLY,
    P1,
    P2,
    P3,
    classify_ioc_disposition,
)


def test_control_api_is_p1_block():
    """精确控制接口是最强可处置指标 -> P1/block。"""
    assert classify_ioc_disposition("control_api", "fezhx.com/api.php") == (P1, BLOCK)


def test_download_path_is_p1_block():
    assert classify_ioc_disposition("download_path", "fnik75tv.com/down24") == (P1, BLOCK)


def test_frontend_domain_is_p1_block():
    """仿冒前台域可直接处置 -> P1/block。"""
    assert classify_ioc_disposition("domain", "apple-app.com.cn") == (P1, BLOCK)


def test_payload_hash_is_p2_block():
    """载荷哈希是文件侧即时拦截对象 -> P2/block。"""
    assert classify_ioc_disposition("imphash", "9b760feffec4fca9c313889f9a05ee36") == (P2, BLOCK)
    assert classify_ioc_disposition("sha256", "9569536b0039") == (P2, BLOCK)


def test_analytics_id_is_p3_correlate_only():
    """51.LA 是合法统计服务, 只能聚类不能封整站 -> P3/correlate_only。"""
    assert classify_ioc_disposition("analytics_id", "3Q3R0HhFsRZ06Tr8") == (P3, CORRELATE_ONLY)


def test_cert_san_is_p3_correlate_only():
    """共享多-SAN 证书是聚类连接件, 非可封禁对象 -> P3/correlate_only。"""
    assert classify_ioc_disposition("cert_san", "shared-SAN:a|b") == (P3, CORRELATE_ONLY)


def test_cloudflare_ip_is_p3_correlate_only():
    """Cloudflare 共享边缘地址整 IP 封禁会误伤合法业务 -> P3/correlate_only。"""
    assert classify_ioc_disposition("ip", "172.67.74.226") == (P3, CORRELATE_ONLY)
    assert classify_ioc_disposition("ip", "104.21.16.1") == (P3, CORRELATE_ONLY)


def test_dedicated_host_ip_is_p2_block():
    """专用下载宿主 IP (非 Cloudflare 段) 可处置 -> P2/block。"""
    assert classify_ioc_disposition("ip", "67.230.179.117") == (P2, BLOCK)
    assert classify_ioc_disposition("ip", "47.239.114.137") == (P2, BLOCK)


def test_unknown_type_defaults_to_correlate_only():
    """未知类型保守作观察池, 仅聚类。"""
    assert classify_ioc_disposition("asn", "AS12345") == (P3, CORRELATE_ONLY)
    assert classify_ioc_disposition("mystery", None) == (P3, CORRELATE_ONLY)
