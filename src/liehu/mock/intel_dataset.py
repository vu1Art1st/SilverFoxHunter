"""情报数据集 (16 篇同作者手记的 intel_reports + 全量 IOC 目录)。

对应文章链接指向的 7/15 → 7/25 同一战役的多日时间序列 (文章 14 即系统
7·23 基线)。本模块以结构化常量收录:

    - INTEL_REPORTS: 16 篇文章的元数据 (slug/标题/日期/阶段/置信边界/外部锚点)。
    - RAW_IOCS     : 跨全部文章归一化的 IOC 目录 (控制域/下载端点/供包池/前台/
                     分析ID/证书/载荷哈希), 每条经 classify_ioc_disposition 打上
                     P1/P2/P3 优先级与 block / correlate_only 处置类别。

这些数据仅用于 seed 入库 (intel_reports / iocs 两张情报表), 不并入 143 前台
基线, 不引入任何 live 采集或样本执行。
"""

from __future__ import annotations

from ..analysis.ioc_priority import classify_ioc_disposition

WECHAT_BASE = "https://mp.weixin.qq.com/s/"

# ---- 16 篇文章 (intel_reports) ----------------------------------------------
# confidence: 置信边界表 (confirmed=已确认 / high=高置信 / not_yet=尚未确认)。
# source_anchors: 外部归因锚点 (仅作数据字段, 不写 live 采集器)。
INTEL_REPORTS: list[dict] = [
    {
        "slug": "D-Pbx_ABlOketT3R7tf8sA",
        "title": "银狐仿冒下载站追踪方法论: P1/P2/P3 与仅聚类不封禁",
        "published_at": "2026-07-15T20:00:00+08:00",
        "campaign_phase": "methodology",
        "summary": "提出 IOC 三级优先级 (精确控制接口/当前下载路径/前台域为 P1) 与共享基础设施 (Cloudflare/51.LA/ASN/NS) 只聚类不封禁的处置边界, 并引入外部归因锚点。",
        "confidence": {
            "confirmed": ["控制接口 api.php 为强连接件", "共享基础设施误封会伤及合法业务"],
            "high": ["51.LA 分析 ID 可用于跨站聚类"],
            "not_yet": ["运营方现实身份"],
        },
        "source_anchors": [
            {"name": "MalwareBazaar", "ref": "银狐/SilverFox 样本族"},
            {"name": "CNCERT", "ref": "仿冒下载站通报"},
            {"name": "奇安信", "ref": "银狐团伙分析"},
        ],
    },
    {
        "slug": "4l2jg6u9q7k8bi3ER1kzVg",
        "title": "从一个仿冒页到控制接口: api.php 连接件",
        "published_at": "2026-07-16T20:00:00+08:00",
        "campaign_phase": "control_pivot",
        "summary": "仿冒前台在加载时精确请求 <control>/api.php 获取下载链接, 该请求关系是最强的归因连接件。",
        "confidence": {
            "confirmed": ["前台精确请求 api.php"],
            "high": ["noah-admin 与 fezhx 属同一战役"],
            "not_yet": [],
        },
        "source_anchors": [{"name": "MalwareBazaar", "ref": "C2 面板指纹"}],
    },
    {
        "slug": "QXfxh7oEdULJs-tzSnSU8Q",
        "title": "51.LA 分析 ID 聚类: 多子簇的发现",
        "published_at": "2026-07-16T21:30:00+08:00",
        "campaign_phase": "analytics_cluster",
        "summary": "同一批仿冒站复用少量 51.LA 统计 ID, 约 12 个 ID 构成子簇; 51.LA 是合法服务, 只作聚类线索不封禁。",
        "confidence": {
            "confirmed": ["多站共享同一 51.LA ID"],
            "high": ["ID 子簇对应不同批次"],
            "not_yet": ["ID 与运营账户绑定关系"],
        },
        "source_anchors": [],
    },
    {
        "slug": "6rTBG2A30yXhyTRtoxQJ5A",
        "title": "注册时间的两只钟: 现做现用 vs 提前备货",
        "published_at": "2026-07-17T20:00:00+08:00",
        "campaign_phase": "registration_clock",
        "summary": "用 RDAP 注册时间与 URLScan 首见时间的差值区分当天现做现用、提前备货与历史域名重注册, 只看一只钟会误判。",
        "confidence": {
            "confirmed": ["注册与首见存在系统性差值"],
            "high": ["提前备货批次择时启用"],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "Xy65PFzMGU16mjspAkq0Ug",
        "title": "载荷静态解析: MSI / 内嵌 PE / imphash 骨架",
        "published_at": "2026-07-17T22:00:00+08:00",
        "campaign_phase": "payload_analysis",
        "summary": "对下发的 MSI 做静态解析, 内嵌 PE 的 imphash 9b760fef... 跨全程稳定, 是生产骨架指纹。",
        "confidence": {
            "confirmed": ["imphash 跨多日稳定"],
            "high": ["WiX 打包骨架同源"],
            "not_yet": [],
        },
        "source_anchors": [{"name": "MalwareBazaar", "ref": "9569536b... 样本"}],
    },
    {
        "slug": "K5juzgFbtWOwtQJzMZ3swg",
        "title": "稳定区哈希: 对抗末尾字节轮换",
        "published_at": "2026-07-18T20:00:00+08:00",
        "campaign_phase": "stable_hash",
        "summary": "样本通过追加末尾字节秒级更换完整 SHA-256, 去尾字节的稳定区哈希才能锁定同一结构。",
        "confidence": {
            "confirmed": ["完整哈希高频轮换", "稳定区哈希保持不变"],
            "high": [],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "2egu_wm5ecKCpLgfmNGJyQ",
        "title": "前台批次: VPN / 办公 / 证券主题轮换",
        "published_at": "2026-07-18T21:30:00+08:00",
        "campaign_phase": "frontend_batch",
        "summary": "同一批次前台按主题 (VPN/办公/证券/AI 工具) 轮换品牌, 复用同一控制接口与分析 ID。",
        "confidence": {
            "confirmed": ["批次内共享控制接口"],
            "high": ["主题轮换为规避识别"],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "tuzdMOgjWVPlP7pcr4X6tw",
        "title": "品牌元数据轮换: Ali → Amazon → Google",
        "published_at": "2026-07-19T20:00:00+08:00",
        "campaign_phase": "brand_rotation",
        "summary": "安装包 Manufacturer 元数据在多日间轮换 (Ali/Amazon/Google/Feitunan Client Dll), 而结构骨架不变。",
        "confidence": {
            "confirmed": ["Manufacturer 字段多次改写"],
            "high": ["元数据轮换与结构解耦"],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "Ra2XigxNM3FOGblKMeDbpQ",
        "title": "预置下载池: 同秒注册连号与共享 SAN 证书",
        "published_at": "2026-07-20T20:00:00+08:00",
        "campaign_phase": "download_pool",
        "summary": "多个下载域同秒注册、序号连号, 且共享同一张多-SAN TLS 证书, 构成预置下载池。",
        "confidence": {
            "confirmed": ["下载域共享多-SAN 证书", "同秒注册连号"],
            "high": ["下载池为择时启用备货"],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "pmf9894ZXtF4oiMB3PARFg",
        "title": "Cloudflare 边缘与共享托管 IP: 为何只聚类",
        "published_at": "2026-07-20T22:00:00+08:00",
        "campaign_phase": "shared_infra",
        "summary": "前台大量落在 Cloudflare 边缘地址段与共享托管 IP, 整 IP 封禁会误伤合法业务, 只能结合 SNI/Host 作聚类。",
        "confidence": {
            "confirmed": ["前台落 Cloudflare 共享段"],
            "high": [],
            "not_yet": ["专用下载宿主 IP 归属"],
        },
        "source_anchors": [],
    },
    {
        "slug": "gNgHxRQF2YFd-40L1kHevw",
        "title": "物流与 Apple Music 主题四站",
        "published_at": "2026-07-21T20:00:00+08:00",
        "campaign_phase": "frontend_batch",
        "summary": "物流四站接 fezhx、Apple Music 四站 14 秒内注册接 noah, 展示同批次秒级注册节奏。",
        "confidence": {
            "confirmed": ["四站秒级注册"],
            "high": ["批次分别归属 noah/fezhx"],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "g3WfmN2Iraitr1EXWZHVCg",
        "title": "下载端点迁移: /712down → /22setup",
        "published_at": "2026-07-22T14:00:00+08:00",
        "campaign_phase": "download_migration",
        "summary": "控制端下发的下载路径由 gehie246.com/712down 迁移到 gnrrn2821.com/22setup, 端点迁移是强信号。",
        "confidence": {
            "confirmed": ["下载端点由 712down 迁移到 22setup"],
            "high": [],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "dOBNx_PWmlqN_ew9b6Zf4Q",
        "title": "控制域接管: page-admin 被 Hold, fezhx 逐字节继承",
        "published_at": "2026-07-22T20:00:00+08:00",
        "campaign_phase": "control_takeover",
        "summary": "page-admin.site 被 serverHold 后, 同日注册的 fezhx.com 以逐字节相同的响应体接管控制面并继承前台。",
        "confidence": {
            "confirmed": ["fezhx 响应体与 page-admin 逐字节相同", "fezhx 继承前台引用"],
            "high": ["fezhx 为 page-admin 的接管方"],
            "not_yet": [],
        },
        "source_anchors": [{"name": "CNCERT", "ref": "page-admin.site serverHold"}],
    },
    {
        "slug": "57xNlAd77AtK4RqvjSa5wg",
        "title": "7·23 晚间水位: 143 前台与路径合流 (系统基线)",
        "published_at": "2026-07-23T19:36:43+08:00",
        "campaign_phase": "route_merge",
        "summary": "去重后 143 前台 (111 noah / 32 fezhx), 控制线合流到 gnrrn2821.com/22setup, 载荷 9.1MB→6.9MB 结构换代, imphash 保持。",
        "confidence": {
            "confirmed": ["143 前台水位", "路径合流到 22setup", "结构换代"],
            "high": [],
            "not_yet": [],
        },
        "source_anchors": [
            {"name": "MalwareBazaar", "ref": "9569536b0039412115aab58dfa315a1f71af1b7294326ccbf7411fc3d26fa292"},
        ],
    },
    {
        "slug": "YI3D2RZmL8ct2jEzH-4NHg",
        "title": "失败请求即控制证据: 引用数≠在线数, 新入口 /down24",
        "published_at": "2026-07-24T20:00:00+08:00",
        "campaign_phase": "online_vs_reference",
        "summary": "noah 被 171 个前台引用但已 NXDOMAIN, 真正在线的是 fezhx; 失败请求本身就是控制证据。新下载入口 fnik75tv.com/down24 上线。",
        "confidence": {
            "confirmed": ["noah 引用数 171 但 NXDOMAIN", "fezhx 才是在线控制面"],
            "high": ["引用数不等于在线数"],
            "not_yet": [],
        },
        "source_anchors": [],
    },
    {
        "slug": "2-AqeVLcp9F92-GScg2c9w",
        "title": "死链投递: /26load 被 Hold 后控制端仍下发",
        "published_at": "2026-07-25T20:00:00+08:00",
        "campaign_phase": "dead_link_delivery",
        "summary": "gukc3u2.com/26load 被 client hold 后控制端仍下发该死链, 客户端拿到 HTTP200+76 字节错误页 (非真包), 而供包后端仍在打包。元数据现 Feitunan Client Dll。",
        "confidence": {
            "confirmed": ["控制端下发已 Hold 的下载域", "HTTP200+76字节非真包"],
            "high": ["供包后端仍在打包"],
            "not_yet": [],
        },
        "source_anchors": [{"name": "奇安信", "ref": "Feitunan Client Dll 元数据"}],
    },
]


# ---- 全量 IOC 目录 (RAW_IOCS) -----------------------------------------------
# 每条为原始情报 (priority_tier / disposition 在 build_iocs 中由分级模块计算)。
IMPHASH = "9b760feffec4fca9c313889f9a05ee36"
MALWAREBAZAAR_SHA256 = "9569536b0039412115aab58dfa315a1f71af1b7294326ccbf7411fc3d26fa292"
EMBEDDED_PE_SHA256_0723 = "57ffe2785f5d5e0720cddf947dcf03f55cae87cceefa20e192fab00b8f21a00e"
STABLE_SHA256_0723 = "a1f58c99d1159e8f0410eff6686ce3836eb1fb274232499d2d176d7071c3ff61"

# 供包池共享多-SAN 证书 (聚类连接件, 非可封禁对象)
_POOL_CERT_SAN = "shared-SAN:gehie246.com|gnrrn2821.com|fnik75tv.com|gukc3u2.com"

RAW_IOCS: list[dict] = [
    # -- 控制接口生命周期 (ioc_type=control_api, 承载 active/held/nxdomain + succeeds) --
    {"ioc_type": "control_api", "value": "page-admin.site/api.php", "campaign": "page",
     "status": "held", "succeeds": None, "first_report_date": "2026-07-15",
     "report_slug": "4l2jg6u9q7k8bi3ER1kzVg", "notes": "历史主控, 7·22 被 serverHold"},
    {"ioc_type": "control_api", "value": "noah-admin.site/api.php", "campaign": "noah",
     "status": "nxdomain", "succeeds": None, "first_report_date": "2026-07-16",
     "report_slug": "4l2jg6u9q7k8bi3ER1kzVg", "notes": "7·24 已 NXDOMAIN, 但仍被 171 前台引用"},
    {"ioc_type": "control_api", "value": "fezhx.com/api.php", "campaign": "fezhx",
     "status": "active", "succeeds": "page-admin.site", "first_report_date": "2026-07-22",
     "report_slug": "dOBNx_PWmlqN_ew9b6Zf4Q", "notes": "响应体与 page-admin 逐字节相同, 接管控制面并继承前台"},

    # -- 下载端点 (ioc_type=download_path, /712down->/22setup->/down24->/26load) --
    {"ioc_type": "download_path", "value": "gehie246.com/712down", "campaign": "page",
     "status": "held", "succeeds": None, "first_report_date": "2026-07-22",
     "report_slug": "g3WfmN2Iraitr1EXWZHVCg", "notes": "最早下载端点, 迁移前"},
    {"ioc_type": "download_path", "value": "www.gnrrn2821.com/22setup", "campaign": "fezhx",
     "status": "active", "succeeds": "gehie246.com", "first_report_date": "2026-07-22",
     "report_slug": "g3WfmN2Iraitr1EXWZHVCg", "notes": "7·23 合流落点"},
    {"ioc_type": "download_path", "value": "fnik75tv.com/down24", "campaign": "fezhx",
     "status": "active", "succeeds": "www.gnrrn2821.com", "first_report_date": "2026-07-24",
     "report_slug": "YI3D2RZmL8ct2jEzH-4NHg", "notes": "7·24 新下载入口"},
    {"ioc_type": "download_path", "value": "gukc3u2.com/26load", "campaign": "fezhx",
     "status": "held", "succeeds": "fnik75tv.com", "first_report_date": "2026-07-25",
     "report_slug": "2-AqeVLcp9F92-GScg2c9w", "notes": "被 client hold 后控制端仍下发 (死链投递)"},
    {"ioc_type": "download_path", "value": "360down.net/Install_asz0.zip", "campaign": "noah",
     "status": "held", "succeeds": None, "first_report_date": "2026-07-22",
     "report_slug": "dOBNx_PWmlqN_ew9b6Zf4Q", "notes": "7·22 noah 旧路线"},

    # -- 供包池下载域 (ioc_type=domain) --
    {"ioc_type": "domain", "value": "gehie246.com", "campaign": "page", "status": "held",
     "succeeds": None, "first_report_date": "2026-07-22", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员 (同秒注册连号)"},
    {"ioc_type": "domain", "value": "gnrrn2821.com", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-22", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员"},
    {"ioc_type": "domain", "value": "fnik75tv.com", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-24", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员"},
    {"ioc_type": "domain", "value": "gukc3u2.com", "campaign": "fezhx", "status": "held",
     "succeeds": None, "first_report_date": "2026-07-25", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员 (7·25 client hold)"},
    {"ioc_type": "domain", "value": "dashte4173.com", "campaign": "fezhx", "status": "unknown",
     "succeeds": None, "first_report_date": "2026-07-20", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员 (预置未启用)"},
    {"ioc_type": "domain", "value": "rubne1877.com", "campaign": "fezhx", "status": "unknown",
     "succeeds": None, "first_report_date": "2026-07-20", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员 (预置未启用)"},
    {"ioc_type": "domain", "value": "whur1584.com", "campaign": "fezhx", "status": "unknown",
     "succeeds": None, "first_report_date": "2026-07-20", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池成员 (预置未启用)"},
    {"ioc_type": "domain", "value": "360down.net", "campaign": "noah", "status": "held",
     "succeeds": None, "first_report_date": "2026-07-22", "report_slug": "g3WfmN2Iraitr1EXWZHVCg",
     "notes": "noah 旧下载宿主"},
    {"ioc_type": "domain", "value": "360down.cn", "campaign": "noah", "status": "held",
     "succeeds": None, "first_report_date": "2026-07-22", "report_slug": "g3WfmN2Iraitr1EXWZHVCg",
     "notes": "noah 旧下载宿主 (.cn 变体)"},

    # -- 控制域裸域 (ioc_type=domain) --
    {"ioc_type": "domain", "value": "page-admin.site", "campaign": "page", "status": "nxdomain",
     "succeeds": None, "first_report_date": "2026-07-15", "report_slug": "dOBNx_PWmlqN_ew9b6Zf4Q",
     "notes": "历史主控裸域"},
    {"ioc_type": "domain", "value": "noah-admin.site", "campaign": "noah", "status": "nxdomain",
     "succeeds": None, "first_report_date": "2026-07-16", "report_slug": "YI3D2RZmL8ct2jEzH-4NHg",
     "notes": "7·24 NXDOMAIN, 仍被 171 前台引用"},
    {"ioc_type": "domain", "value": "fezhx.com", "campaign": "fezhx", "status": "active",
     "succeeds": "page-admin.site", "first_report_date": "2026-07-22", "report_slug": "dOBNx_PWmlqN_ew9b6Zf4Q",
     "notes": "现役控制裸域"},

    # -- 代表性前台域 (ioc_type=domain, 不并入 143 基线) --
    {"ioc_type": "domain", "value": "lets-vpn.com.cn", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-18", "report_slug": "2egu_wm5ecKCpLgfmNGJyQ",
     "notes": "VPN 主题前台 (历史域重注册)"},
    {"ioc_type": "domain", "value": "hp-driver.com.cn", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-18", "report_slug": "2egu_wm5ecKCpLgfmNGJyQ",
     "notes": "惠普驱动主题前台"},
    {"ioc_type": "domain", "value": "jianying-app.com.cn", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-19", "report_slug": "tuzdMOgjWVPlP7pcr4X6tw",
     "notes": "剪映主题前台"},
    {"ioc_type": "domain", "value": "instagram-cn.com.cn", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-19", "report_slug": "tuzdMOgjWVPlP7pcr4X6tw",
     "notes": "Instagram 主题前台"},
    {"ioc_type": "domain", "value": "steam-dl.com.cn", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-19", "report_slug": "2egu_wm5ecKCpLgfmNGJyQ",
     "notes": "Steam 主题前台"},
    {"ioc_type": "domain", "value": "foxit-reader.com.cn", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-18", "report_slug": "2egu_wm5ecKCpLgfmNGJyQ",
     "notes": "Foxit 办公主题前台"},
    {"ioc_type": "domain", "value": "sf-tracking.com.cn", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-21", "report_slug": "gNgHxRQF2YFd-40L1kHevw",
     "notes": "物流主题前台 (顺丰)"},
    {"ioc_type": "domain", "value": "apple-app.com.cn", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-21", "report_slug": "gNgHxRQF2YFd-40L1kHevw",
     "notes": "Apple Music 主题前台 (14 秒内注册)"},

    # -- 专用下载宿主 IP (ioc_type=ip, 非 Cloudflare -> P2/block) --
    {"ioc_type": "ip", "value": "67.230.179.117", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-22", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "专用下载宿主 IP"},
    {"ioc_type": "ip", "value": "47.239.114.137", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-24", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "专用下载宿主 IP"},
    # -- Cloudflare 共享边缘 (ioc_type=ip -> P3/correlate_only) --
    {"ioc_type": "ip", "value": "172.67.74.226", "campaign": "unknown", "status": "unknown",
     "succeeds": None, "first_report_date": "2026-07-20", "report_slug": "pmf9894ZXtF4oiMB3PARFg",
     "notes": "Cloudflare 共享边缘, 只能结合 SNI/Host 聚类"},
    {"ioc_type": "ip", "value": "104.21.16.1", "campaign": "unknown", "status": "unknown",
     "succeeds": None, "first_report_date": "2026-07-20", "report_slug": "pmf9894ZXtF4oiMB3PARFg",
     "notes": "Cloudflare 共享边缘"},

    # -- 共享多-SAN 证书 (ioc_type=cert_san -> P3/correlate_only) --
    {"ioc_type": "cert_san", "value": _POOL_CERT_SAN, "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-20", "report_slug": "Ra2XigxNM3FOGblKMeDbpQ",
     "notes": "供包池共享多-SAN 证书 (强聚类连接件)"},

    # -- 51.LA 分析 ID (ioc_type=analytics_id -> P3/correlate_only) 约 12 个子簇 --
    {"ioc_type": "analytics_id", "value": "3Q3R0HhFsRZ06Tr8", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-16", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "fezhx 主 ID"},
    {"ioc_type": "analytics_id", "value": "3QLy6y8xrBsoHT2R", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-16", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "noah 主 ID"},
    {"ioc_type": "analytics_id", "value": "3QbHsAGVXQpa2nIl", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-16", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3QbvgmKU4mQXDLRW", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-16", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3QViwtwaxrxmBATa", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-17", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3QIMielUrIaXc63E", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-17", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3Qc7OwPw19YYEuAZ", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-18", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3QdmEnEYMGRUR9tn", "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-18", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3QLN0kIEw9jU1Vcr", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-19", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},
    {"ioc_type": "analytics_id", "value": "3QFPOqGI5sDH2uDR", "campaign": "noah", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-19", "report_slug": "QXfxh7oEdULJs-tzSnSU8Q", "notes": "子簇 ID"},

    # -- 载荷哈希 (ioc_type=imphash / sha256 -> P2/block) --
    {"ioc_type": "imphash", "value": IMPHASH, "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-17", "report_slug": "Xy65PFzMGU16mjspAkq0Ug",
     "notes": "生产骨架 imphash, 跨 7/15-7/25 稳定"},
    {"ioc_type": "sha256", "value": MALWAREBAZAAR_SHA256, "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-23", "report_slug": "57xNlAd77AtK4RqvjSa5wg",
     "notes": "MalwareBazaar 完整样本 SHA-256"},
    {"ioc_type": "sha256", "value": EMBEDDED_PE_SHA256_0723, "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-23", "report_slug": "57xNlAd77AtK4RqvjSa5wg",
     "notes": "7·23 内嵌 PE SHA-256"},
    {"ioc_type": "sha256", "value": STABLE_SHA256_0723, "campaign": "fezhx", "status": "active",
     "succeeds": None, "first_report_date": "2026-07-23", "report_slug": "K5juzgFbtWOwtQJzMZ3swg",
     "notes": "7·23 去尾字节稳定区 SHA-256"},
]


def build_reports() -> list[dict]:
    """返回 16 篇文章的入库行 (补齐 url 字段, confidence/anchors 保持原生结构)。"""
    rows: list[dict] = []
    for r in INTEL_REPORTS:
        rows.append({
            "slug": r["slug"],
            "url": WECHAT_BASE + r["slug"],
            "title": r["title"],
            "published_at": r["published_at"],
            "campaign_phase": r["campaign_phase"],
            "summary": r["summary"],
            "confidence": r["confidence"],
            "source_anchors": r["source_anchors"],
        })
    return rows


def build_iocs() -> list[dict]:
    """返回全量 IOC 入库行, 每条经 classify_ioc_disposition 打上 (priority_tier, disposition)。"""
    rows: list[dict] = []
    for ioc in RAW_IOCS:
        tier, disposition = classify_ioc_disposition(ioc["ioc_type"], ioc.get("value"))
        rows.append({
            **ioc,
            "priority_tier": tier,
            "disposition": disposition,
        })
    return rows
