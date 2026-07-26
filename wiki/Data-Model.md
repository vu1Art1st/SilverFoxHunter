# 数据模型

← 返回 [Wiki 首页](Home.md)

存储采用 Python 内置 `sqlite3`（WAL 模式），零外部依赖、单文件。全部建表 DDL 见
[`src/liehu/db.py`](../src/liehu/db.py) 的 `SCHEMA`；领域枚举见 [`src/liehu/models.py`](../src/liehu/models.py)。

## 表总览

| 表 | 层 | 说明 |
|----|----|------|
| `frontends` | 壳 | 前台页面状态卡，按 `domain` 主键 upsert |
| `control_samples` | 线 | 控制接口 `api.php` 分时采样 |
| `payloads` | 包 | 载荷（MSI/内嵌 PE）静态解析结构指标 |
| `dns_snapshots` | 线 | DNS 解析生命周期快照 |
| `events` | — | 差异事件（只推变化） |
| `links` | 关联 | 壳→线→包关系图边 |
| `errors` | — | 采集错误账本 |
| `meta` | — | 键值元数据（mock 回放轮次指针等） |

## frontends（壳 · 前台状态卡）

主键 `domain`（归一化后的 `page.domain`），采集到同域名时 upsert。

| 字段 | 类型 | 说明 |
|------|------|------|
| `domain` | TEXT PK | 归一化域名 |
| `first_seen` / `last_seen` | TEXT | 首次 / 最近记录时间（ISO） |
| `title` | TEXT | 当前页面标题 |
| `page_ip` / `http_status` | TEXT / INT | 主页面 IP、HTTP 状态 |
| `control_domain` / `control_api` | TEXT | 请求的控制接口域名 / 完整 URL（线连接件） |
| `analytics_id` | TEXT | 51.LA 等分析 ID（线连接件） |
| `theme` | TEXT | 题材：office/vpn/logistics/music… |
| `registered_at` | TEXT | 注册时间（RDAP/WHOIS） |
| `ns` | TEXT | NS 记录（逗号分隔） |
| `day_class` | TEXT | 当天分类，见枚举 `DayClass` |
| `campaign` | TEXT | 归因战役：noah/fezhx/unknown |
| `evidence_url` | TEXT | 原始证据链接 |
| `task_uuid` | TEXT | URLScan `task.uuid`（去重键） |
| `updated_at` | TEXT | 落库时间 |

## control_samples（线 · 控制接口采样）

自增主键，同一 `control_api` 多条记录构成时间线，用于观测 `download_link` 从分离到合流。

关键字段：`control_domain` / `control_api` / `observed_at` / `http_status` /
`resp_sha256`（响应体哈希）/ `resp_length` / `download_link`（解析出的下载地址）/
`headers_json` / `error`（采集失败原因，不视为变化事件）。

## payloads（包 · 载荷结构指纹）

每次静态解析一条记录。**完整哈希秒级轮换，结构骨架持久** —— 这正是稳定区哈希的价值所在。

| 字段 | 说明 |
|------|------|
| `download_url` | 下载地址（如 `gnrrn2821.com/22setup`） |
| `full_sha256` | 完整文件 SHA-256（秒级轮换，末尾字节 006f/007f/008f） |
| `stable_sha256` | 去尾字节后的**稳定区** SHA-256（锁定生产骨架） |
| `embedded_pe_sha256` / `embedded_pe_size` | 内嵌 PE 哈希 / 大小 |
| `imphash` | 导入哈希 |
| `pe_entry_rva` | PE 入口 RVA |
| `msi_size` | MSI 文件大小 |
| `ole_stream_count` / `ole_identical` | OLE 流总数 / 与上一轮逐字节一致的流数 |
| `wix_version` | 安装器元数据（如 WiX 4.0.5.0） |
| `structure_id` | 生产骨架标识（结构指纹分组键） |

## dns_snapshots（线 · DNS 快照）

`domain` / `observed_at` / `dns_status`（Google DoH Status：0=NOERROR、3=NXDOMAIN）/
`a_records` / `aaaa_records` / `cname_records` / `ns_records`（记录以 JSON 存储）。

## events（差异事件 · 只推变化）

系统产出的不是快照而是**差异事件流**。

| 字段 | 说明 |
|------|------|
| `event_type` | 事件类型，见枚举 `EventType` |
| `object_ref` | 关联对象（域名 / 接口 / 下载路径） |
| `priority` | 优先级：high / pending / watch |
| `first_observed` / `last_observed` | 首次 / 最近观察时间 |
| `prev_state` / `curr_state` | 上一状态 / 当前状态 |
| `fact` | 触发该事件的事实 |
| `evidence_url` | 证据链接 |
| `created_at` | 事件生成时间 |

## links（关联 · 关系图边）

`UNIQUE(src, dst, relation)` 保证边幂等。字段：`src` / `src_type` / `dst` / `dst_type` /
`relation`（requests/binds/returns/rotates）/ `campaign`。节点类型见枚举 `NodeType`。

## errors（采集错误账本）

`source`（urlscan/rdap/dns/control/payload）/ `target` / `reason`
（quota/invisible/whois_timeout/servfail…）/ `observed_at`。**错误与 IOC 同等重要**：
配额耗尽、隐身失败都会影响水位判断。

## meta（运行时状态）

`key` / `value` 键值对，记录 mock 回放轮次指针等，保证多次触发 `trigger` 时按序推进时间线。

---

## 领域枚举（models.py）

- **`EventType`**：`NEW_FRONTEND` / `FIRST_PUBLIC` / `CONTENT_CHANGE` / `CONTROL_CHANGE` /
  `ROUTE_MERGE` / `ROUTE_SPLIT` / `PAYLOAD_ROTATION` / `PAYLOAD_STRUCTURAL_CHANGE` / `STATUS_CHANGE`
- **`Priority`**：`high`（精确控制接口、当前下载路径、结构换代）/ `pending`（多项连接件共现）/
  `watch`（仅共享 IP/ASN/注册商/NS/模板）
- **`DayClass`**：`same_day` / `preexisting` / `rescan` / `content_change`
- **`Campaign`**：`noah` / `fezhx` / `unknown`（**仅技术聚类，不指向现实身份**）
- **`NodeType`**：`frontend`（壳）/ `control` / `analytics` / `download`（线）/ `payload`（包）
- **DNS 状态常量**：`DNS_NOERROR=0`、`DNS_NXDOMAIN=3`

---

延伸阅读：[API 参考](API-Reference.md) · [核心方法论](Methodology.md) · [系统架构](Architecture.md)
