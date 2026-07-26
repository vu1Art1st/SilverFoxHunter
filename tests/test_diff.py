"""差异引擎单元测试 (对应文章第六节: 告警只推变化)。"""

from __future__ import annotations

from liehu.analysis.diff import (
    diff_control,
    diff_dns,
    diff_frontend,
    diff_payload,
)
from liehu.models import EventType


def test_diff_frontend_new_emits_two_events():
    """新前台 -> NEW_FRONTEND + FIRST_PUBLIC。"""
    curr = {
        "domain": "apple-app.com.cn",
        "control_api": "noah-admin.site/api.php",
        "first_seen": "2026-07-23T10:00:00",
    }
    events = diff_frontend(None, curr)
    types = {e["event_type"] for e in events}
    assert types == {EventType.NEW_FRONTEND, EventType.FIRST_PUBLIC}


def test_diff_frontend_content_change():
    prev = {"domain": "a.com", "title": "旧标题", "page_ip": "1.1.1.1"}
    curr = {"domain": "a.com", "title": "新标题", "page_ip": "1.1.1.1"}
    events = diff_frontend(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.CONTENT_CHANGE


def test_diff_frontend_no_change():
    same = {"domain": "a.com", "title": "t", "page_ip": "1.1.1.1",
            "http_status": 200, "control_api": "x/api.php"}
    assert diff_frontend(dict(same), dict(same)) == []


def test_diff_control_change_on_download_link():
    prev = {"control_api": "noah-admin.site/api.php", "download_link": "old/22setup"}
    curr = {"control_api": "noah-admin.site/api.php", "download_link": "www.gnrrn2821.com/22setup"}
    events = diff_control(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.CONTROL_CHANGE


def test_diff_control_ignores_error_and_first_sample():
    assert diff_control(None, {"control_api": "x", "download_link": "y"}) == []
    assert diff_control({"download_link": "a"}, {"control_api": "x", "error": "NXDOMAIN"}) == []


def _payload(full, structure="skeleton-9.1MB", stable="STABLE-A", pe="PE-A"):
    return {
        "download_url": "www.gnrrn2821.com/22setup",
        "full_sha256": full,
        "stable_sha256": stable,
        "embedded_pe_sha256": pe,
        "imphash": "9b760feffec4fca9c313889f9a05ee36",
        "structure_id": structure,
        "pe_entry_rva": 5790106,
        "ole_stream_count": 25,
        "ole_identical": 22,
    }


def test_diff_payload_rotation():
    prev = _payload("HASH-006f")
    curr = _payload("HASH-007f")
    events = diff_payload(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.PAYLOAD_ROTATION


def test_diff_payload_structural_change_takes_priority():
    prev = _payload("HASH-A", structure="skeleton-9.1MB")
    curr = _payload("HASH-B", structure="skeleton-6.9MB", stable="STABLE-B", pe="PE-B")
    events = diff_payload(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.PAYLOAD_STRUCTURAL_CHANGE


def test_diff_dns_status_change():
    prev = {"domain": "page-admin.site", "dns_status": 0, "a_records": ["1.1.1.1"], "ns_records": []}
    curr = {"domain": "page-admin.site", "dns_status": 3, "a_records": [], "ns_records": []}
    events = diff_dns(prev, curr)
    types = [e["event_type"] for e in events]
    assert EventType.STATUS_CHANGE in types
