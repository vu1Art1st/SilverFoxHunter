"""差异引擎 (对应文章"告警只推变化")。

diff 函数均为纯函数: 接收上一状态 (prev) 与当前状态 (curr), 返回差异事件列表。
不直接读写数据库, 便于单元测试。事件的持久化与优先级分配由上层 (store/alerting)
完成。
"""

from __future__ import annotations

from .stablehash import is_pure_rotation, is_structural_change
from ..models import EventType


def _event(event_type: str, object_ref: str, fact: str,
           prev_state: str | None, curr_state: str | None,
           evidence_url: str | None = None) -> dict:
    return {
        "event_type": event_type,
        "object_ref": object_ref,
        "fact": fact,
        "prev_state": prev_state,
        "curr_state": curr_state,
        "evidence_url": evidence_url,
    }


def diff_frontend(prev: dict | None, curr: dict) -> list[dict]:
    """前台差异: NEW_FRONTEND / FIRST_PUBLIC / CONTENT_CHANGE。"""
    events: list[dict] = []
    domain = curr["domain"]

    if prev is None:
        # 新页面精确请求已知控制接口
        events.append(_event(
            EventType.NEW_FRONTEND, domain,
            f"新前台精确请求控制接口 {curr.get('control_api')}",
            None, curr.get("control_api"), curr.get("evidence_url"),
        ))
        events.append(_event(
            EventType.FIRST_PUBLIC, domain,
            "首次进入公开扫描记录",
            None, curr.get("first_seen"), curr.get("evidence_url"),
        ))
        return events

    # 已知站: 检测标题 / IP / 状态 / 控制引用变化
    changed_fields = []
    for field, label in [
        ("title", "标题"), ("page_ip", "IP"),
        ("http_status", "HTTP状态"), ("control_api", "控制接口引用"),
    ]:
        if prev.get(field) != curr.get(field):
            changed_fields.append((field, label))

    if changed_fields:
        labels = ", ".join(lbl for _, lbl in changed_fields)
        prev_state = "; ".join(f"{f}={prev.get(f)}" for f, _ in changed_fields)
        curr_state = "; ".join(f"{f}={curr.get(f)}" for f, _ in changed_fields)
        events.append(_event(
            EventType.CONTENT_CHANGE, domain,
            f"已知站 {labels} 发生改变",
            prev_state, curr_state, curr.get("evidence_url"),
        ))
    return events


def diff_control(prev: dict | None, curr: dict) -> list[dict]:
    """控制端差异: CONTROL_CHANGE (响应体或 download_link 改变)。"""
    if curr.get("error"):
        return []  # 采集失败交由 errors 表, 不作为变化事件
    if prev is None:
        return []  # 首次采样不算变化
    if (prev.get("download_link") != curr.get("download_link")
            or prev.get("resp_sha256") != curr.get("resp_sha256")):
        return [_event(
            EventType.CONTROL_CHANGE, curr["control_api"],
            "API 响应体或 download_link 改变",
            prev.get("download_link"), curr.get("download_link"),
        )]
    return []


def diff_payload(prev: dict | None, curr: dict) -> list[dict]:
    """载荷差异: PAYLOAD_STRUCTURAL_CHANGE 优先于 PAYLOAD_ROTATION。"""
    if prev is None:
        return []
    # 结构换代优先判断 (更高优先级)
    if is_structural_change(prev, curr):
        return [_event(
            EventType.PAYLOAD_STRUCTURAL_CHANGE, curr["download_url"],
            f"生产骨架结构换代 {prev.get('structure_id')} -> {curr.get('structure_id')}",
            prev.get("stable_sha256"), curr.get("stable_sha256"),
        )]
    if is_pure_rotation(prev, curr):
        return [_event(
            EventType.PAYLOAD_ROTATION, curr["download_url"],
            "完整哈希轮换, 稳定结构保持",
            prev.get("full_sha256"), curr.get("full_sha256"),
        )]
    return []


def diff_dns(prev: dict | None, curr: dict) -> list[dict]:
    """DNS 差异: STATUS_CHANGE (NXDOMAIN/恢复解析/地址或NS改变)。"""
    if prev is None:
        return []
    events: list[dict] = []
    if prev.get("dns_status") != curr.get("dns_status"):
        events.append(_event(
            EventType.STATUS_CHANGE, curr["domain"],
            f"DNS Status {prev.get('dns_status')} -> {curr.get('dns_status')}",
            str(prev.get("dns_status")), str(curr.get("dns_status")),
        ))
    if prev.get("a_records") != curr.get("a_records"):
        events.append(_event(
            EventType.STATUS_CHANGE, curr["domain"],
            "A 记录集合改变",
            str(prev.get("a_records")), str(curr.get("a_records")),
        ))
    if prev.get("ns_records") != curr.get("ns_records"):
        events.append(_event(
            EventType.STATUS_CHANGE, curr["domain"],
            "NS 集合改变",
            str(prev.get("ns_records")), str(curr.get("ns_records")),
        ))
    return events
