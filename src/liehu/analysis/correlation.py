"""关联分析 / 追踪定位 (对应文章第二、六节)。

两个核心能力:
1. 多时钟分类: 用注册时间 (RDAP) 与首次公开记录 (URLScan/CT) 把"当天现做现用"
   与"提前备货、择时启用"分开; 历史域名重新注册后启用单列。
2. 连接件归因: 精确控制接口、相同分析 ID、秒级注册节奏、相邻地址等"多项同时对上"
   才进入关联集合; 仅共享 IP/ASN/注册商/NS/模板的先留作候选。

同时负责构建"壳->线->包"关系图的边 (links)。
"""

from __future__ import annotations

from datetime import datetime

from ..models import Campaign, DayClass, NodeType

# 文章案例的基线日期 (北京时间 7·23)
BASELINE_DATE = "2026-07-23"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def classify_registration(
    registered_at: str | None,
    first_seen: str | None,
    baseline_date: str = BASELINE_DATE,
) -> str:
    """根据注册时间与首见时间的多时钟关系分类。

    返回值:
        same_day    : 当天注册且当天进入公开记录 (现做现用)
        preexisting : 注册早于基线, 当天才进入本次查询 (提前备货)
        reactivated : 历史域名重新注册后启用 (首见远早于注册)
    """
    reg = _parse_date(registered_at)
    seen = _parse_date(first_seen)

    # 历史域名重新注册: 公开扫描早于本次注册 (只看一只钟会误判)
    if reg and seen and seen.date() < reg.date():
        return "reactivated"

    if reg and reg.strftime("%Y-%m-%d") == baseline_date:
        return DayClass.SAME_DAY
    return DayClass.PREEXISTING


# ---- 连接件归因 --------------------------------------------------------------

# 连接件权重: 精确控制接口 / 共享证书 / 分析 ID 为强连接件; IP/NS 仅候选
PIECE_WEIGHTS = {
    "control_api": 5,     # 精确 api.php 请求关系 (最强)
    "shared_cert": 4,     # 共享多-SAN TLS 证书 (下载池强连接件)
    "analytics_id": 3,    # 相同分析 ID
    "adjacent_reg": 2,    # 秒级注册节奏 + 相邻地址
    "shared_ip": 1,       # 仅共享 IP (候选)
    "shared_ns": 1,       # 仅共享 NS (候选)
}

# 已知控制接口 -> 战役映射
CONTROL_CAMPAIGN = {
    "noah-admin.site/api.php": Campaign.NOAH,
    "fezhx.com/api.php": Campaign.FEZHX,
    "page-admin.site/api.php": Campaign.PAGE,   # 历史主控 (7·22 serverHold)
}


def attribute_campaign(control_api: str | None) -> str:
    """基于精确控制接口归因到战役标签 (仅技术聚类, 不指向现实身份)。"""
    if not control_api:
        return Campaign.UNKNOWN
    return CONTROL_CAMPAIGN.get(control_api, Campaign.UNKNOWN)


def confidence(pieces: dict[str, bool]) -> tuple[str, int]:
    """根据命中的连接件计算置信度。

    Args:
        pieces: {piece_name: hit?} 例如 {"control_api": True, "analytics_id": True}

    Returns:
        (level, score)
        level: "confirmed" (可进入关联集合) 或 "candidate" (先留作候选)
        score: 连接件加权得分
    """
    score = sum(PIECE_WEIGHTS.get(name, 0) for name, hit in pieces.items() if hit)
    # 命中精确控制接口或共享证书即可确认; 或分析ID+其它连接件共现
    strong = pieces.get("control_api") or pieces.get("shared_cert") or (
        pieces.get("analytics_id") and pieces.get("adjacent_reg")
    )
    level = "confirmed" if strong else "candidate"
    return level, score


def detect_adjacent_registration(records: list[dict], window_seconds: int = 10) -> list[list[str]]:
    """检测秒级注册节奏 (批处理痕迹)。

    找出注册时间彼此相差在 window_seconds 内的域名分组 (如 Apple Music 四站
    14 秒内注册)。
    """
    dated = [
        (r["domain"], _parse_date(r.get("registered_at")))
        for r in records if r.get("registered_at")
    ]
    dated = [(d, t) for d, t in dated if t is not None]
    dated.sort(key=lambda x: x[1])

    groups: list[list[str]] = []
    current: list[str] = []
    prev_time: datetime | None = None
    for domain, t in dated:
        if prev_time is not None and (t - prev_time).total_seconds() <= window_seconds:
            current.append(domain)
        else:
            if len(current) >= 2:
                groups.append(current)
            current = [domain]
        prev_time = t
    if len(current) >= 2:
        groups.append(current)
    return groups


# ---- 关系图 (壳->线->包) ------------------------------------------------------

def normalize_download(link: str | None) -> str | None:
    """归一化下载路径节点 id: 去掉协议前缀与末尾斜杠。

    mock 数据源与文章 IOC 均使用 "host/path" 形式 (如 360down.net/Install_asz0.zip),
    而 live 控制端采样返回完整 URL (如 https://360down.net/xxx.zip); 若不归一化,
    同一宿主会在关联图中分裂为两个下载路径节点, 造成图与列表数据不一致。
    """
    if not link:
        return link
    normalized = link.strip()
    for scheme in ("https://", "http://"):
        if normalized.lower().startswith(scheme):
            normalized = normalized[len(scheme):]
            break
    return normalized.rstrip("/")


def build_links(
    frontends: list[dict],
    control_samples: list[dict],
    payloads: list[dict],
) -> list[dict]:
    """构建"壳->线->包"关系图的边。

    边类型:
        frontend --requests--> control     (壳 请求 控制接口)
        frontend --binds-----> analytics   (壳 绑定 分析ID)
        control  --returns----> download    (控制接口 返回 下载路径)
        download --rotates----> payload     (下载路径 落下 载荷样本)
    """
    links: list[dict] = []
    seen: set[tuple] = set()

    def add(src, src_type, dst, dst_type, relation, campaign):
        key = (src, dst, relation)
        if dst and key not in seen:
            seen.add(key)
            links.append({
                "src": src, "src_type": src_type,
                "dst": dst, "dst_type": dst_type,
                "relation": relation, "campaign": campaign,
            })

    for f in frontends:
        campaign = f.get("campaign", Campaign.UNKNOWN)
        add(f["domain"], NodeType.FRONTEND, f.get("control_api"),
            NodeType.CONTROL, "requests", campaign)
        add(f["domain"], NodeType.FRONTEND, f.get("analytics_id"),
            NodeType.ANALYTICS, "binds", campaign)

    for s in control_samples:
        if s.get("download_link"):
            campaign = CONTROL_CAMPAIGN.get(s.get("control_api"), Campaign.UNKNOWN)
            add(s["control_api"], NodeType.CONTROL, normalize_download(s["download_link"]),
                NodeType.DOWNLOAD, "returns", campaign)

    for p in payloads:
        if p.get("structure_id"):
            add(normalize_download(p["download_url"]), NodeType.DOWNLOAD, p["structure_id"],
                NodeType.PAYLOAD, "rotates", Campaign.UNKNOWN)

    return links


def detect_route_topology(samples_by_round: list[list[dict]]) -> list[dict]:
    """检测控制线的合流 / 分流 (ROUTE_MERGE / ROUTE_SPLIT)。

    对比相邻两轮采样: 若两条原本不同 download_link 的控制线在新一轮返回同一路径,
    记 ROUTE_MERGE; 反之记 ROUTE_SPLIT。
    """
    events: list[dict] = []
    for i in range(1, len(samples_by_round)):
        prev = {s["control_api"]: s.get("download_link") for s in samples_by_round[i - 1]}
        curr = {s["control_api"]: s.get("download_link") for s in samples_by_round[i]}

        prev_distinct = len({v for v in prev.values() if v})
        curr_links = [v for v in curr.values() if v]
        curr_distinct = len(set(curr_links))

        if prev_distinct > 1 and curr_distinct == 1 and len(curr_links) > 1:
            events.append({
                "type": "ROUTE_MERGE",
                "download_link": curr_links[0],
                "control_apis": [k for k, v in curr.items() if v],
            })
        elif prev_distinct == 1 and curr_distinct > 1:
            events.append({
                "type": "ROUTE_SPLIT",
                "control_apis": [k for k, v in curr.items() if v],
            })
    return events


# ---- 控制域接管 / 下载池 -------------------------------------------------

def detect_control_succession(control_samples: list[dict]) -> list[dict]:
    """检测控制域接管 (对应文章 7·22 page-admin -> fezhx)。

    当一个控制域的成功响应 (resp_sha256) 与另一个处于 held/nxdomain
    状态的控制域最后一份成功响应逐字节相同时, 认为新域接管了旧域。

    Args:
        control_samples: 控制端采样列表, 每项含 control_domain / control_api /
            resp_sha256 / status (active/held/nxdomain) / observed_at。

    Returns:
        继承关系列表, 每项: {successor, predecessor, resp_sha256}。
    """
    # 按响应体哈希归集
    by_hash: dict[str, list[dict]] = {}
    for s in control_samples:
        digest = s.get("resp_sha256")
        if digest:
            by_hash.setdefault(digest, []).append(s)

    events: list[dict] = []
    for digest, group in by_hash.items():
        if len(group) < 2:
            continue
        # 处于 held/nxdomain 的为前任; active 的为接管方
        predecessors = [g for g in group if g.get("status") in ("held", "nxdomain")]
        successors = [g for g in group if g.get("status") == "active"]
        for succ in successors:
            for pred in predecessors:
                if succ.get("control_domain") == pred.get("control_domain"):
                    continue
                events.append({
                    "successor": succ.get("control_domain"),
                    "predecessor": pred.get("control_domain"),
                    "resp_sha256": digest,
                })
    return events


def detect_download_pool(
    records: list[dict], window_seconds: int = 5
) -> list[list[str]]:
    """检测预置下载池 (对应文章 gnrrn/dashte/fnik75tv/gukc3u2 同秒注册)。

    同一池的判据: 共享同一张多-SAN 证书 (cert_san) 且注册时间落在
    window_seconds 窗口内 (或共享同一下载宿主 IP)。仅共享 IP 而无证书/
    同秒注册的不单独成池。

    Args:
        records: 下载域记录, 每项含 domain / cert_san / registered_at / download_ip。

    Returns:
        每个子列表为一个池的域名集合 (至少 2 个)。
    """
    # 1) 按共享 SAN 证书聚类 (强连接件)
    by_cert: dict[str, list[dict]] = {}
    for r in records:
        san = r.get("cert_san")
        if san:
            by_cert.setdefault(san, []).append(r)

    pools: list[list[str]] = []
    grouped: set[str] = set()
    for san, group in by_cert.items():
        if len(group) >= 2:
            domains = [g["domain"] for g in group]
            pools.append(domains)
            grouped.update(domains)

    # 2) 剩余未分组的: 同秒注册 + 相同下载 IP
    rest = [r for r in records if r["domain"] not in grouped]
    adjacent = detect_adjacent_registration(rest, window_seconds)
    ip_of = {r["domain"]: r.get("download_ip") for r in rest}
    for grp in adjacent:
        ips = {ip_of.get(d) for d in grp if ip_of.get(d)}
        if len(ips) == 1:  # 同秒注册且落在同一下载 IP
            pools.append(grp)

    return pools
