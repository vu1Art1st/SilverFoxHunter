"""模拟数据集 (从文章 7·23 晚间水位复原)。

该模块复原文章《我是怎么追踪银狐新域名的》中 2026-07-23 19:36:43 (北京时间)
的观测水位, 作为 Mock Provider 的数据源, 使系统在无任何 API Key 的情况下即可
完整运行并触发差异事件 (ROUTE_MERGE / PAYLOAD_STRUCTURAL_CHANGE / PAYLOAD_ROTATION)。

复原的关键事实:
    - 去重后 143 个前台: 111 接入 noah, 32 接入 fezhx
    - 当天分类: 11 同日注册并活跃 / 113 本次首见 / 9 复扫 / 10 内容变化
    - 4 个物流主题前台共享 fezhx/api.php + 51.LA 3Q3R0HhFsRZ06Tr8
    - Apple Music 四站 14 秒内注册 (同日活跃, noah)
    - 控制线 7·22 分离 -> 7·23 合流到 gnrrn2821.com/22setup
    - 载荷 MSI 9.1MB 结构 -> 6.9MB 结构换代, 随后末尾字节制造哈希轮换
"""

from __future__ import annotations

from ..models import Campaign, DayClass

# ---- 控制接口 (线) -----------------------------------------------------------
CONTROL_NOAH = "noah-admin.site"
CONTROL_FEZHX = "fezhx.com"
CONTROL_PAGE = "page-admin.site"  # 历史控制接口, 7·23 三轮为 NXDOMAIN

CONTROL_API_NOAH = "noah-admin.site/api.php"
CONTROL_API_FEZHX = "fezhx.com/api.php"
CONTROL_API_PAGE = "page-admin.site/api.php"

# ---- 分析 ID -----------------------------------------------------------------
ANALYTICS_FEZHX = "3Q3R0HhFsRZ06Tr8"
ANALYTICS_NOAH = "3QLy6y8xrBsoHT2R"

# ---- 下载路径 (线) -----------------------------------------------------------
DOWNLOAD_GNRRN = "www.gnrrn2821.com/22setup"
DOWNLOAD_360 = "360down.net/Install_asz0.zip"  # 7·22 noah 旧路线

# ---- 载荷 IOC (包) -----------------------------------------------------------
IMPHASH = "9b760feffec4fca9c313889f9a05ee36"
EMBEDDED_PE_SHA256_0723 = (
    "57ffe2785f5d5e0720cddf947dcf03f55cae87cceefa20e192fab00b8f21a00e"
)
STABLE_SHA256_0723 = (
    "a1f58c99d1159e8f0410eff6686ce3836eb1fb274232499d2d176d7071c3ff61"
)

# ---- 物流主题四站 (文章表格原文) ----------------------------------------------
LOGISTICS_FRONTENDS = [
    {
        "domain": "sf-tracking.com.cn",
        "registered_at": "2026-07-23T12:15:09+08:00",
        "first_seen": "2026-07-23T19:29:00+08:00",
        "page_ip": "186.240.117.137",
        "title": "顺丰-全球包裹查询",
        "theme": "logistics",
    },
    {
        "domain": "yt-tracking.com.cn",
        "registered_at": "2026-07-23T12:15:05+08:00",
        "first_seen": "2026-07-23T19:29:55+08:00",
        "page_ip": "186.240.117.138",
        "title": "圆通-全球包裹查询",
        "theme": "logistics",
    },
    {
        "domain": "ems-track.com.cn",
        "registered_at": "2026-07-23T12:02:12+08:00",
        "first_seen": "2026-07-23T19:31:16+08:00",
        "page_ip": "156.250.163.199",
        "title": "EMS 包裹查询",
        "theme": "logistics",
    },
    {
        "domain": "ems-track.hl.cn",
        "registered_at": "2026-07-23T12:02:07+08:00",
        "first_seen": "2026-07-23T19:32:44+08:00",
        "page_ip": "156.250.163.200",
        "title": "EMS 全球包裹查询",
        "theme": "logistics",
    },
]

# ---- Apple Music 四站 (同日 14 秒内注册, noah) --------------------------------
APPLE_FRONTENDS = [
    {
        "domain": "apple-app.com.cn",
        "registered_at": "2026-07-23T19:03:19+08:00",
        "first_seen": "2026-07-23T19:22:15+08:00",
        "page_ip": "156.250.163.201",
        "title": "Apple Music 官方下载",
        "theme": "music",
    },
    {
        "domain": "apple-ap.com.cn",
        "registered_at": "2026-07-23T19:03:24+08:00",
        "first_seen": "2026-07-23T19:22:41+08:00",
        "page_ip": "156.250.163.202",
        "title": "Apple Music 官方下载",
        "theme": "music",
    },
    {
        "domain": "apple-yinyue.com.cn",
        "registered_at": "2026-07-23T19:03:29+08:00",
        "first_seen": "2026-07-23T19:23:10+08:00",
        "page_ip": "156.250.163.203",
        "title": "Apple 音乐客户端",
        "theme": "music",
    },
    {
        "domain": "musicapple.com.cn",
        "registered_at": "2026-07-23T19:03:33+08:00",
        "first_seen": "2026-07-23T19:23:38+08:00",
        "page_ip": "156.250.163.204",
        "title": "Apple Music 下载",
        "theme": "music",
    },
]

# 历史域名重新注册后启用 (lets-vpn), 用于演示"只看一只钟会误判"
REACTIVATED_FRONTENDS = [
    {
        "domain": "lets-vpn.com.cn",
        "registered_at": "2026-07-23T19:18:14+08:00",
        "first_seen": "2025-11-02T08:11:00+08:00",  # URLScan 留有 2025 旧扫描
        "page_ip": "156.250.163.210",
        "title": "LetsVPN 官方下载",
        "theme": "vpn",
        "day_class": DayClass.CONTENT_CHANGE,
    },
]

# 各题材模板 (用于程序化补齐前台池)
THEMES = ["office", "vpn", "securities", "music", "ai_tool", "logistics"]
THEME_TITLES = {
    "office": "办公软件官方下载",
    "vpn": "VPN 客户端下载",
    "securities": "证券交易软件下载",
    "music": "音乐客户端下载",
    "ai_tool": "AI 工具官方下载",
    "logistics": "全球包裹查询",
}


def _base_ip(index: int) -> str:
    """生成用于填充的共享托管地址 (仅候选线索, 不作归因)。"""
    return f"156.250.{160 + index % 32}.{50 + index % 200}"


def generate_frontends() -> list[dict]:
    """生成 143 个前台记录, 满足文章的战役与当天分类分布。

    分布:
        战役: noah 111 / fezhx 32
        当天分类: same_day 11 / preexisting 113 / rescan 9 / content_change 10
    """
    records: list[dict] = []

    # 1) 物流四站 -> fezhx, 同日注册并活跃
    for i, f in enumerate(LOGISTICS_FRONTENDS):
        records.append({
            **f,
            "task_uuid": f"uuid-logi-{i:03d}",
            "http_status": 200,
            "control_domain": CONTROL_FEZHX,
            "control_api": CONTROL_API_FEZHX,
            "analytics_id": ANALYTICS_FEZHX,
            "campaign": Campaign.FEZHX,
            "day_class": DayClass.SAME_DAY,
            "ns": "ns1.dnspod.net,ns2.dnspod.net",
            "last_seen": "2026-07-23T19:36:00+08:00",
            "evidence_url": f"https://urlscan.io/result/uuid-logi-{i:03d}/",
        })

    # 2) Apple Music 四站 -> noah, 同日注册并活跃
    for i, f in enumerate(APPLE_FRONTENDS):
        records.append({
            **f,
            "task_uuid": f"uuid-apple-{i:03d}",
            "http_status": 200,
            "control_domain": CONTROL_NOAH,
            "control_api": CONTROL_API_NOAH,
            "analytics_id": ANALYTICS_NOAH,
            "campaign": Campaign.NOAH,
            "day_class": DayClass.SAME_DAY,
            "ns": "ns3.dnsv5.com,ns4.dnsv5.com",
            "last_seen": "2026-07-23T19:36:10+08:00",
            "evidence_url": f"https://urlscan.io/result/uuid-apple-{i:03d}/",
        })

    # 3) 历史域名重新注册后启用
    for i, f in enumerate(REACTIVATED_FRONTENDS):
        base = {k: v for k, v in f.items() if k != "day_class"}
        records.append({
            **base,
            "task_uuid": f"uuid-react-{i:03d}",
            "http_status": 200,
            "control_domain": CONTROL_NOAH,
            "control_api": CONTROL_API_NOAH,
            "analytics_id": ANALYTICS_NOAH,
            "campaign": Campaign.NOAH,
            "day_class": f["day_class"],
            "ns": "ns3.dnsv5.com,ns4.dnsv5.com",
            "last_seen": "2026-07-23T19:34:00+08:00",
            "evidence_url": f"https://urlscan.io/result/uuid-react-{i:03d}/",
        })

    # 目前显式记录: 4 (logi,fezhx) + 4 (apple,noah,same_day) + 1 (react,noah,content_change)
    # 已用: fezhx=4, noah=5 ; same_day=8, content_change=1
    # 需补齐到: noah=111, fezhx=32 ; same_day=11, content_change=10, rescan=9, preexisting=113

    # 计数器
    counts_campaign = {Campaign.FEZHX: 4, Campaign.NOAH: 5}
    counts_dayclass = {
        DayClass.SAME_DAY: 8,
        DayClass.CONTENT_CHANGE: 1,
        DayClass.RESCAN: 0,
        DayClass.PREEXISTING: 0,
    }
    target_campaign = {Campaign.FEZHX: 32, Campaign.NOAH: 111}
    target_dayclass = {
        DayClass.SAME_DAY: 11,
        DayClass.CONTENT_CHANGE: 10,
        DayClass.RESCAN: 9,
        DayClass.PREEXISTING: 113,
    }

    # 生成剩余当天分类的有序列表
    remaining_dayclasses: list[str] = []
    for dc, target in target_dayclass.items():
        remaining_dayclasses += [dc] * (target - counts_dayclass[dc])
    # remaining 应为 134 个 (143 - 9 显式)
    idx = 0
    for dc in remaining_dayclasses:
        # 战役分配: 优先补足 fezhx 到 32, 其余归 noah
        if counts_campaign[Campaign.FEZHX] < target_campaign[Campaign.FEZHX]:
            campaign = Campaign.FEZHX
        else:
            campaign = Campaign.NOAH
        counts_campaign[campaign] += 1

        theme = THEMES[idx % len(THEMES)]
        is_fezhx = campaign == Campaign.FEZHX
        control_domain = CONTROL_FEZHX if is_fezhx else CONTROL_NOAH
        control_api = CONTROL_API_FEZHX if is_fezhx else CONTROL_API_NOAH
        analytics = ANALYTICS_FEZHX if is_fezhx else ANALYTICS_NOAH

        # 根据当天分类决定注册/首见时间
        if dc == DayClass.PREEXISTING:
            registered_at = f"2026-07-{10 + idx % 12:02d}T08:00:00+08:00"
            first_seen = "2026-07-23T19:20:00+08:00"
        elif dc == DayClass.SAME_DAY:
            registered_at = "2026-07-23T14:00:00+08:00"
            first_seen = "2026-07-23T19:25:00+08:00"
        elif dc == DayClass.RESCAN:
            registered_at = f"2026-07-{5 + idx % 10:02d}T08:00:00+08:00"
            first_seen = "2026-07-22T10:00:00+08:00"
        else:  # content_change
            registered_at = f"2026-07-{8 + idx % 10:02d}T08:00:00+08:00"
            first_seen = "2026-07-21T10:00:00+08:00"

        records.append({
            "domain": f"{theme}-dl-{idx:03d}.com.cn",
            "task_uuid": f"uuid-gen-{idx:04d}",
            "registered_at": registered_at,
            "first_seen": first_seen,
            "last_seen": "2026-07-23T19:35:00+08:00",
            "page_ip": _base_ip(idx),
            "http_status": 200 if dc != DayClass.CONTENT_CHANGE else 302,
            "title": THEME_TITLES[theme],
            "theme": theme,
            "control_domain": control_domain,
            "control_api": control_api,
            "analytics_id": analytics,
            "campaign": campaign,
            "day_class": dc,
            "ns": "ns1.dnspod.net,ns2.dnspod.net" if is_fezhx else "ns3.dnsv5.com,ns4.dnsv5.com",
            "evidence_url": f"https://urlscan.io/result/uuid-gen-{idx:04d}/",
        })
        idx += 1

    return records


# ---- 控制端分时采样回放 (线) --------------------------------------------------
# 每一轮为一个"照片"。系统按轮次前进, 从 7·22 的分离状态过渡到 7·23 的合流。
CONTROL_ROUNDS = [
    # 7·22 晚间: 两条控制线分离
    {
        "observed_at": "2026-07-22T19:56:00+08:00",
        "samples": [
            {"control_domain": CONTROL_NOAH, "control_api": CONTROL_API_NOAH,
             "http_status": 200, "download_link": DOWNLOAD_360},
            {"control_domain": CONTROL_FEZHX, "control_api": CONTROL_API_FEZHX,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_PAGE, "control_api": CONTROL_API_PAGE,
             "http_status": 200, "download_link": DOWNLOAD_360},
        ],
    },
    # 7·23 19:23:46 第一轮: noah 切入同一落点 -> ROUTE_MERGE
    {
        "observed_at": "2026-07-23T19:23:46+08:00",
        "samples": [
            {"control_domain": CONTROL_NOAH, "control_api": CONTROL_API_NOAH,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_FEZHX, "control_api": CONTROL_API_FEZHX,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_PAGE, "control_api": CONTROL_API_PAGE,
             "http_status": None, "download_link": None, "error": "NXDOMAIN"},
        ],
    },
    # 7·23 19:27:15 第二轮
    {
        "observed_at": "2026-07-23T19:27:15+08:00",
        "samples": [
            {"control_domain": CONTROL_NOAH, "control_api": CONTROL_API_NOAH,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_FEZHX, "control_api": CONTROL_API_FEZHX,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_PAGE, "control_api": CONTROL_API_PAGE,
             "http_status": None, "download_link": None, "error": "NXDOMAIN"},
        ],
    },
    # 7·23 19:30:51 第三轮
    {
        "observed_at": "2026-07-23T19:30:51+08:00",
        "samples": [
            {"control_domain": CONTROL_NOAH, "control_api": CONTROL_API_NOAH,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_FEZHX, "control_api": CONTROL_API_FEZHX,
             "http_status": 200, "download_link": DOWNLOAD_GNRRN},
            {"control_domain": CONTROL_PAGE, "control_api": CONTROL_API_PAGE,
             "http_status": None, "download_link": None, "error": "NXDOMAIN"},
        ],
    },
]


# ---- 载荷分时观测回放 (包) ----------------------------------------------------
# 同一晚出现两类变化: 先 9.1MB -> 6.9MB 结构换代, 随后新结构上末尾字节制造哈希轮换。
PAYLOAD_ROUNDS = [
    # 7·22 样本: 9.1MB 结构
    {
        "observed_at": "2026-07-22T20:10:00+08:00",
        "download_url": DOWNLOAD_GNRRN,
        "full_sha256": "22aa" + "0" * 60,
        "msi_size": 9158656,
        "embedded_pe_size": 9116101,
        "pe_entry_rva": 5790106,
        "stable_sha256": "fd523b" + "e" * 58,
        "embedded_pe_sha256": "fd523b0000" + "e" * 54,
        "imphash": IMPHASH,
        "ole_stream_count": 25,
        "ole_identical": 25,
        "wix_version": "4.0.5.0",
        "structure_id": "skeleton-9.1MB",
    },
    # 7·23 结构换代: 6.9MB 结构 -> PAYLOAD_STRUCTURAL_CHANGE
    {
        "observed_at": "2026-07-23T19:23:00+08:00",
        "download_url": DOWNLOAD_GNRRN,
        "full_sha256": "23bb" + "1" * 60,
        "msi_size": 6975488,
        "embedded_pe_size": 6937036,
        "pe_entry_rva": 3149792,
        "stable_sha256": STABLE_SHA256_0723,
        "embedded_pe_sha256": EMBEDDED_PE_SHA256_0723,
        "imphash": IMPHASH,       # 生产骨架保留
        "ole_stream_count": 25,
        "ole_identical": 22,      # 22/25 逐字节一致
        "wix_version": "4.0.5.0",
        "structure_id": "skeleton-6.9MB",
    },
    # 7·23 后续: 末尾字节制造新完整哈希, 但稳定区不变 -> PAYLOAD_ROTATION (006f)
    {
        "observed_at": "2026-07-23T19:28:00+08:00",
        "download_url": DOWNLOAD_GNRRN,
        "full_sha256": "23cc006f" + "2" * 56,
        "msi_size": 6975488,
        "embedded_pe_size": 6937036,
        "pe_entry_rva": 3149792,
        "stable_sha256": STABLE_SHA256_0723,   # 稳定区保持
        "embedded_pe_sha256": EMBEDDED_PE_SHA256_0723,
        "imphash": IMPHASH,
        "ole_stream_count": 25,
        "ole_identical": 25,
        "wix_version": "4.0.5.0",
        "structure_id": "skeleton-6.9MB",
    },
    # 7·23 再一轮轮换 (007f)
    {
        "observed_at": "2026-07-23T19:32:00+08:00",
        "download_url": DOWNLOAD_GNRRN,
        "full_sha256": "23dd007f" + "3" * 56,
        "msi_size": 6975488,
        "embedded_pe_size": 6937036,
        "pe_entry_rva": 3149792,
        "stable_sha256": STABLE_SHA256_0723,
        "embedded_pe_sha256": EMBEDDED_PE_SHA256_0723,
        "imphash": IMPHASH,
        "ole_stream_count": 25,
        "ole_identical": 25,
        "wix_version": "4.0.5.0",
        "structure_id": "skeleton-6.9MB",
    },
]


# ---- DNS 快照回放 -------------------------------------------------------------
DNS_SNAPSHOTS = {
    CONTROL_PAGE: {  # 历史控制接口, 三轮 NXDOMAIN
        "dns_status": 3,
        "a_records": [],
        "ns_records": [],
    },
    CONTROL_NOAH: {
        "dns_status": 0,
        "a_records": ["156.250.163.180"],
        "ns_records": ["ns3.dnsv5.com", "ns4.dnsv5.com"],
    },
    CONTROL_FEZHX: {
        "dns_status": 0,
        "a_records": ["186.240.117.130"],
        "ns_records": ["ns1.dnspod.net", "ns2.dnspod.net"],
    },
}


def starting_iocs() -> dict:
    """返回文章"留给运营侧的起始指标"(对应 7·23 晚间水位)。"""
    return {
        "active_control_apis": [CONTROL_API_NOAH, CONTROL_API_FEZHX],
        "historical_control_apis": [CONTROL_API_PAGE],
        "download_path": DOWNLOAD_GNRRN,
        "logistics_frontends": [f["domain"] for f in LOGISTICS_FRONTENDS],
        "analytics_ids": [ANALYTICS_FEZHX, ANALYTICS_NOAH],
        "embedded_pe_sha256": EMBEDDED_PE_SHA256_0723,
        "stable_sha256": STABLE_SHA256_0723,
        "imphash": IMPHASH,
    }
