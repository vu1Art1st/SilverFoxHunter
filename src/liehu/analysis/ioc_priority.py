"""IOC 优先级分级与处置类别 (对应文章第一篇的 P1/P2/P3 与"仅聚类不封禁")。

文章把 IOC 分成可以直接处置的高价值指标 (精确控制接口、当前下载路径、仿冒前台)
与只能"关联但不封禁"的共享基础设施 (Cloudflare IP、51.LA 统计服务、ASN/NS、
共享托管 IP)。后者若整 IP/整服务封禁会误伤合法业务, 只作聚类线索。

本模块提供纯函数 classify_ioc_disposition, 输入 IOC 类型 (与值), 返回
(priority_tier, disposition), 供入库时给每条 IOC 打标。
"""

from __future__ import annotations

# 处置类别
BLOCK = "block"                    # 可直接处置 (封禁/拦截)
CORRELATE_ONLY = "correlate_only"  # 仅聚类, 不封禁 (共享基础设施)

# 优先级层级
P1 = "P1"  # 最高: 精确控制接口 / 当前下载路径 / 仿冒前台域
P2 = "P2"  # 次高: 批次域 / 分析ID / 供包池成员 / 载荷哈希
P3 = "P3"  # 观察: 共享基础设施 (Cloudflare/51.LA/ASN/NS/共享 IP)

# 仅聚类不封禁的共享基础设施 IOC 类型
_CORRELATE_ONLY_TYPES = {
    "analytics_id",  # 51.LA 是合法统计服务, 不能因此封整站
    "cert_san",      # 证书 SAN 是聚类连接件, 非可封禁对象
    "asn",
    "ns",
}

# Cloudflare 边缘地址段前缀 (共享基础设施, 只能结合 SNI/Host 使用, 不能整 IP 封禁)
_CLOUDFLARE_PREFIXES = ("104.21.", "172.67.", "172.66.", "172.64.", "104.16.")


def _is_cloudflare(value: str | None) -> bool:
    """判断 IP 是否落在 Cloudflare 共享边缘地址段。"""
    if not value:
        return False
    return value.strip().startswith(_CLOUDFLARE_PREFIXES)


def classify_ioc_disposition(ioc_type: str, value: str | None = None) -> tuple[str, str]:
    """根据 IOC 类型 (与值) 返回 (priority_tier, disposition)。

    规则:
        - control_api / download_path / url  -> P1 / block
        - domain (仿冒前台或下载域)          -> P1 / block
        - sha256 / imphash                    -> P2 / block (文件侧即时拦截)
        - analytics_id / cert_san / ns / asn  -> P3 / correlate_only
        - ip: Cloudflare 共享段 -> P3 / correlate_only; 其余专用宿主 -> P2 / block

    Args:
        ioc_type: IOC 类型标签。
        value: IOC 值 (用于 IP 的 Cloudflare 判定)。
    """
    t = (ioc_type or "").strip().lower()

    if t in ("control_api", "download_path", "url"):
        return P1, BLOCK
    if t == "domain":
        return P1, BLOCK
    if t in ("sha256", "imphash"):
        return P2, BLOCK
    if t in _CORRELATE_ONLY_TYPES:
        return P3, CORRELATE_ONLY
    if t == "ip":
        # Cloudflare 共享边缘地址只能作聚类; 专用下载宿主 IP 可处置
        if _is_cloudflare(value):
            return P3, CORRELATE_ONLY
        return P2, BLOCK

    # 未知类型: 保守作观察池, 仅聚类
    return P3, CORRELATE_ONLY
