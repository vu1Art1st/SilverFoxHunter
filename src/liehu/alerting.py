"""告警层 (对应文章第六节"告警只推变化" + 差异卡)。

职责:
    - 为每个差异事件分配优先级 (高优 / 待确认 / 观察池);
    - 生成"差异卡": 对象、首次与最近观察时间、上一状态、当前状态、变化类型、
      证据链接和覆盖缺口, 供值班同事消费 (企业微信 / 邮件 / SIEM)。
"""

from __future__ import annotations

from .models import EventType, Priority

# 事件类型 -> 优先级 (对应文章优先级口径)
#   高优: 精确控制接口、当前下载路径、结构换代
#   待确认: 分析ID、秒级注册、相邻地址等多项共现
#   观察池: 仅共享 IP/ASN/注册商/NS/模板
EVENT_PRIORITY = {
    EventType.NEW_FRONTEND: Priority.HIGH,            # 精确请求已知控制接口
    EventType.CONTROL_CHANGE: Priority.HIGH,          # 控制通信改变
    EventType.ROUTE_MERGE: Priority.HIGH,             # 下载路径与战役拓扑
    EventType.ROUTE_SPLIT: Priority.HIGH,
    EventType.PAYLOAD_STRUCTURAL_CHANGE: Priority.HIGH,  # EDR 补检和分析升级
    EventType.CONTROL_TAKEOVER: Priority.HIGH,        # 控制面继承 (新域接管被 Hold 旧域)
    EventType.DOWNLOAD_MIGRATION: Priority.HIGH,      # 下载宿主/路径迁移
    EventType.DEAD_LINK_DELIVERY: Priority.HIGH,      # 控制端下发死链, 供包后端仍活跃
    EventType.FIRST_PUBLIC: Priority.PENDING,
    EventType.CONTENT_CHANGE: Priority.WATCH,         # 资产状态复核
    EventType.PAYLOAD_ROTATION: Priority.WATCH,       # 更新当轮文件 IOC
    EventType.STATUS_CHANGE: Priority.WATCH,          # DNS 状态监控
}

# 事件类型 -> 建议落点 (对应文章事件表"适合落到哪里")
EVENT_SINK = {
    EventType.NEW_FRONTEND: "DNS / 代理 / 网关的前台预警",
    EventType.FIRST_PUBLIC: "前台预警",
    EventType.CONTENT_CHANGE: "资产状态复核",
    EventType.CONTROL_CHANGE: "控制通信拦截",
    EventType.ROUTE_MERGE: "下载路径与战役拓扑告警",
    EventType.ROUTE_SPLIT: "下载路径与战役拓扑告警",
    EventType.PAYLOAD_ROTATION: "更新当轮文件 IOC, 保留结构检索",
    EventType.PAYLOAD_STRUCTURAL_CHANGE: "EDR 补检和分析升级",
    EventType.CONTROL_TAKEOVER: "控制面继承告警",
    EventType.DOWNLOAD_MIGRATION: "下载路径迁移告警",
    EventType.DEAD_LINK_DELIVERY: "死链投递/供包后端仍活跃告警",
    EventType.STATUS_CHANGE: "DNS 状态监控",
}


def priority_for(event_type: str) -> str:
    """返回事件类型对应的优先级。"""
    return EVENT_PRIORITY.get(event_type, Priority.WATCH)


def sink_for(event_type: str) -> str:
    """返回事件类型的建议落点。"""
    return EVENT_SINK.get(event_type, "观察池")


def build_diff_card(event: dict) -> dict:
    """将一条事件渲染为差异卡 (dict)。"""
    etype = event.get("event_type", "")
    return {
        "object": event.get("object_ref"),
        "event_type": etype,
        "priority": event.get("priority") or priority_for(etype),
        "first_observed": event.get("first_observed"),
        "last_observed": event.get("last_observed"),
        "prev_state": event.get("prev_state"),
        "curr_state": event.get("curr_state"),
        "fact": event.get("fact"),
        "sink": sink_for(etype),
        "evidence_url": event.get("evidence_url"),
    }
