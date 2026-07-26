"""领域模型与常量。

定义"壳/线/包"三层数据的内部数据类、事件类型、优先级、当天分类、战役标签
等枚举常量。这些常量直接对应文章中的术语口径。
"""

from __future__ import annotations

from dataclasses import dataclass, field


class EventType:
    """差异事件类型 (对应文章"告警只推变化"一节的事件表)。"""

    NEW_FRONTEND = "NEW_FRONTEND"                       # 新页面精确请求已知控制接口
    FIRST_PUBLIC = "FIRST_PUBLIC"                       # 首次公开记录
    CONTENT_CHANGE = "CONTENT_CHANGE"                   # 标题/IP/状态/控制引用改变
    CONTROL_CHANGE = "CONTROL_CHANGE"                   # API 响应体或 download_link 改变
    ROUTE_MERGE = "ROUTE_MERGE"                         # 分时样本显示控制线合流
    ROUTE_SPLIT = "ROUTE_SPLIT"                         # 控制线分流
    PAYLOAD_ROTATION = "PAYLOAD_ROTATION"               # 完整哈希变, 稳定结构保持
    PAYLOAD_STRUCTURAL_CHANGE = "PAYLOAD_STRUCTURAL_CHANGE"  # MSI流/内嵌PE/稳定区改变
    STATUS_CHANGE = "STATUS_CHANGE"                     # NXDOMAIN/恢复解析/地址或NS改变


class Priority:
    """事件优先级 (对应文章的高优 / 待确认 / 观察池)。"""

    HIGH = "high"        # 精确控制接口、当前下载路径、结构换代
    PENDING = "pending"  # 分析ID、秒级注册、相邻地址等多项共现
    WATCH = "watch"      # 仅共享 IP/ASN/注册商/NS/常见模板


class DayClass:
    """当天分类 (对应文章"注册时间把现做和库存分开")。"""

    SAME_DAY = "same_day"            # 同日注册并活跃
    PREEXISTING = "preexisting"      # 本次有界查询首见 (注册更早)
    RESCAN = "rescan"                # 复扫, 未见关键字段变化
    CONTENT_CHANGE = "content_change"  # 标题/IP/状态发生改变


class Campaign:
    """战役标签。仅作为基于连接件的技术聚类, 不指向现实身份。"""

    NOAH = "noah"
    FEZHX = "fezhx"
    UNKNOWN = "unknown"


class NodeType:
    """关联图节点类型 (壳/线/包)。"""

    FRONTEND = "frontend"     # 壳
    CONTROL = "control"       # 线-控制接口
    ANALYTICS = "analytics"   # 线-分析ID
    DOWNLOAD = "download"     # 线-下载路径
    PAYLOAD = "payload"       # 包-样本结构骨架


# DNS 响应状态 (Google DoH)
DNS_NOERROR = 0
DNS_NXDOMAIN = 3


@dataclass
class FrontendRecord:
    """壳: 一条前台扫描记录 (采集器输出的标准结构)。"""

    domain: str
    task_uuid: str
    first_seen: str | None = None
    last_seen: str | None = None
    title: str | None = None
    page_ip: str | None = None
    http_status: int | None = None
    control_domain: str | None = None
    control_api: str | None = None
    analytics_id: str | None = None
    theme: str | None = None
    registered_at: str | None = None
    ns: str | None = None
    evidence_url: str | None = None


@dataclass
class ControlSampleRecord:
    """线: 一次控制接口采样。"""

    control_domain: str
    control_api: str
    observed_at: str
    http_status: int | None = None
    resp_sha256: str | None = None
    resp_length: int | None = None
    download_link: str | None = None
    headers_json: str | None = None
    error: str | None = None


@dataclass
class PayloadRecord:
    """包: 一次载荷静态解析结果。"""

    download_url: str
    observed_at: str
    full_sha256: str | None = None
    msi_size: int | None = None
    embedded_pe_size: int | None = None
    pe_entry_rva: int | None = None
    stable_sha256: str | None = None
    embedded_pe_sha256: str | None = None
    imphash: str | None = None
    ole_stream_count: int | None = None
    ole_identical: int | None = None
    wix_version: str | None = None
    structure_id: str | None = None


@dataclass
class DnsSnapshotRecord:
    """DNS 快照。"""

    domain: str
    observed_at: str
    dns_status: int | None = None
    a_records: list[str] = field(default_factory=list)
    aaaa_records: list[str] = field(default_factory=list)
    cname_records: list[str] = field(default_factory=list)
    ns_records: list[str] = field(default_factory=list)
