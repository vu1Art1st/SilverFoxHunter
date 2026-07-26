# SilverFoxHunter 银狐猎手 · 系统设计文档

> 银狐 (SilverFox) 仿冒下载链威胁情报追踪系统
> 基于文章《我是怎么追踪银狐新域名的》的"壳 / 线 / 包"三层方法论实现

---

## 1. 背景与技术理念

银狐团伙通过大量**仿冒下载页面**（伪装成物流查询、Apple Music、办公软件、券商、VPN、AI 工具等）
诱导受害者下载木马。这些前台页面**域名更换极快**（当天现做现用），单纯封域名收效甚微。

原文作者提出的核心思路是：**不要盯着变化最快的那一层，而是沿着"壳 → 线 → 包"三层
从易变到持久逐层下沉，抓住相对稳定的"连接件"来关联与追踪。**

### 1.1 三层模型（壳 / 线 / 包）

| 层 | 别名 | 内容 | 易变程度 | 追踪价值 |
|----|------|------|----------|----------|
| **壳** | Shell / 前台 | 仿冒页面域名、标题、品牌题材 | 最快（当天轮换） | 低（单个域名寿命短） |
| **线** | Line / 控制线 | 控制接口 `api.php`、`download_link`、分析 ID、下载路径 | 中（数天~数周） | 高（跨壳复用） |
| **包** | Package / 载荷 | MSI / 内嵌 PE 载荷；完整哈希秒级轮换，但结构骨架持久 | 完整哈希最快 / 骨架最慢 | 高（稳定区哈希锁定生产线） |

### 1.2 核心方法论（对应原文各节）

1. **多时钟关联**：用 4 只"钟"交叉判断域名的真实"年龄"与用途——
   - CT 证书透明日志（CertSpotter）
   - RDAP / WHOIS 注册时间
   - DNS（DoH）解析状态
   - URLScan 首次公开扫描记录

   单看一只钟会误判：例如某域名"首见"早于"注册时间"，其实是**历史域名被重新注册**（reactivated）。

2. **连接件归因**：只有**多项强连接件同时对上**才确认关联，避免噪声聚类：
   - 精确控制接口（`noah-admin.site/api.php`）——最强连接件
   - 相同分析 ID（`3Q3R0HhFsRZ06Tr8`）
   - 秒级注册节奏 + 相邻 IP（批处理痕迹，如 Apple Music 四站数秒内注册）
   - 仅共享 IP / ASN / 注册商 / NS / 模板 → 只作**候选**，不进关联集合

3. **稳定区哈希**：载荷完整哈希（`full_sha256`）秒级轮换（末尾字节 006f/007f/008f），
   去掉不稳定末尾字节后的**稳定区 SHA-256** 才能回答"这批文件来自哪套生产骨架"。
   配合 imphash、内嵌 PE 哈希、OLE 流结构、入口 RVA 共同构成"结构骨架指纹"。

4. **告警只推变化**：持续监控产生的不是快照而是**差异事件流**——只有对象状态发生
   有意义的变化才推送，并按优先级分级（高优 / 待确认 / 观察池），落到不同处置渠道。

### 1.3 复原的 7·23 水位（真实案例数据）

本系统的 mock 数据集**忠实复原**了原文 7·23 晚间的观测水位：

- **143 个前台**：noah 战役 111 个 + fezhx 战役 32 个
- **题材分布**：物流 / Apple Music / 办公 / 券商 / VPN / AI 工具
- **控制线**：`noah-admin.site/api.php`、`fezhx.com/api.php`（活跃），`page-admin.site/api.php`（NXDOMAIN）
- **路径合流**：7·22 两条控制线各自下载路径 → 7·23 合流到 `www.gnrrn2821.com/22setup`（ROUTE_MERGE）
- **载荷换代**：MSI 9,158,656 B → 6,975,488 B（结构换代 1 次）+ 尾字节轮换 2 次
- **稳定指纹**：imphash `9b760feffec4fca9c313889f9a05ee36`、WiX 4.0.5.0、OLE 25 流 22 相同

---

## 2. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Web 仪表盘 (静态 HTML + ECharts)            │
│   总览水位 · 前台(壳) · 控制线(线) · 载荷(包) · 关联图 · 事件流  │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP /api/*
┌───────────────────────────▼──────────────────────────────────┐
│                    展示层 (FastAPI routers)                     │
│   stats · frontends · controls · payloads · events · campaigns │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│              编排层 (tracker) + 调度层 (scheduler)              │
│   run_frontend/control/payload/dns_cycle · APScheduler 分级调度 │
└───────────────┬───────────────────────────┬──────────────────┘
                │                           │
┌───────────────▼──────────────┐  ┌──────────▼───────────────────┐
│   分析层 (analysis)           │  │   告警层 (alerting)           │
│  dedup · correlation          │  │  优先级分级 · 差异卡渲染       │
│  stablehash · diff (纯函数)   │  └──────────────────────────────┘
└───────────────┬──────────────┘
                │
┌───────────────▼──────────────────────────────────────────────┐
│                  采集层 (collectors, Provider 抽象)            │
│  urlscan · certspotter · rdap · doh · control · payload        │
│                mock 模式 (回放) ⇄ live 模式 (真实源)           │
└───────────────┬──────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────┐
│                 数据层 (db, SQLite + WAL)                      │
│  frontends · control_samples · payloads · dns_snapshots         │
│  events · links · errors · meta                                 │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 分层职责

- **采集层**：把外部数据源抽象为统一 `Provider`，每个采集器支持 `mock`/`live` 双模式。
  原始响应先落盘（`data/evidence/`），失败写入 `errors` 账本。
- **分析层**：纯函数实现，不直接读写数据库，便于单元测试。承担去重、多时钟分类、
  连接件归因、稳定区哈希、差异计算。
- **编排层**：`tracker` 把"采集 → 分析 → 落库 → 生成事件"串成一次"追踪周期"。
- **调度层**：`scheduler` 用 APScheduler 按不同层级的节奏分级触发周期。
- **告警层**：为事件分配优先级、渲染差异卡。
- **展示层**：FastAPI 只读接口 + 静态仪表盘。

### 2.2 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言/运行时 | Python ≥ 3.10 | 类型注解、dataclass |
| 环境管理 | **uv** | `uv sync` / `uv run` |
| Web 框架 | FastAPI + uvicorn | 异步、自动 OpenAPI |
| 调度 | APScheduler (BackgroundScheduler) | 分级 cron/interval |
| HTTP 客户端 | httpx | live 模式采集 |
| 载荷解析 | pefile + olefile | PE / MSI(OLE) 静态解析 |
| 存储 | sqlite3（标准库）+ WAL | 零依赖、单文件 |
| 前端 | 原生 HTML/CSS/JS + ECharts 5 | 免构建，静态托管 |
| 测试 | pytest | 单元 + 集成 (TestClient) |

---

## 3. 数据模型（SQLite）

所有表定义见 [`src/liehu/db.py`](../src/liehu/db.py) 的 `SCHEMA`。

| 表 | 层 | 关键字段 | 说明 |
|----|----|---------|------|
| `frontends` | 壳 | `domain`(PK)、`campaign`、`day_class`、`theme`、`control_api`、`analytics_id`、`registered_at`、`first_seen`、`last_seen` | 前台状态卡，按域名 upsert |
| `control_samples` | 线 | `control_api`、`observed_at`、`download_link`、`resp_sha256`、`http_status`、`error` | 控制接口分时采样 |
| `payloads` | 包 | `download_url`、`full_sha256`、`stable_sha256`、`embedded_pe_sha256`、`imphash`、`structure_id`、`msi_size`、`pe_entry_rva`、`ole_stream_count`、`ole_identical` | 载荷静态解析结果 |
| `dns_snapshots` | 线 | `domain`、`dns_status`、`a_records`、`ns_records` | DNS 解析快照 |
| `events` | — | `event_type`、`object_ref`、`priority`、`prev_state`、`curr_state`、`fact` | 差异事件（只推变化） |
| `links` | 关联 | `src`、`src_type`、`dst`、`dst_type`、`relation`、`campaign`（`UNIQUE(src,dst,relation)`） | 壳→线→包关系图边 |
| `errors` | — | `source`、`detail`、`occurred_at` | 采集错误账本 |
| `meta` | — | `key`、`value` | mock 轮次指针等运行时状态 |

### 3.1 领域枚举（[`src/liehu/models.py`](../src/liehu/models.py)）

- `EventType`：`NEW_FRONTEND` / `FIRST_PUBLIC` / `CONTENT_CHANGE` / `CONTROL_CHANGE` /
  `ROUTE_MERGE` / `ROUTE_SPLIT` / `PAYLOAD_ROTATION` / `PAYLOAD_STRUCTURAL_CHANGE` / `STATUS_CHANGE`
- `Priority`：`high` / `pending` / `watch`
- `DayClass`：`same_day` / `preexisting` / `rescan` / `content_change`
- `Campaign`：`noah` / `fezhx` / `unknown`（**仅技术聚类，不指向现实身份**）
- `NodeType`：`frontend` / `control` / `analytics` / `download` / `payload`

---

## 4. 核心模块详解

### 4.1 数据采集模块（`src/liehu/collectors/`）

统一的 `Provider` 基类（[`base.py`](../src/liehu/collectors/base.py)）提供 `mode`/`api_key`/`is_live`
属性、证据落盘 `dump_evidence()`、错误记账 `record_error()` 与 `sha256_hex()` 等工具。
`build_collectors()` 工厂按配置组装全部采集器。

| 采集器 | 数据源 | 层 | mock 行为 | live 行为 |
|--------|--------|----|-----------|-----------|
| `urlscan` | URLScan Search API | 壳 | 从 mock 数据集筛选前台 | 构造 `filename.keyword`/`page.domain` 精确查询 + 重叠时间窗 |
| `certspotter` | CertSpotter CT 日志 | 线 | 回放 CT 首见 | 拉取子域证书 |
| `rdap` | RDAP / WHOIS | 线 | 回放注册时间 | 查询注册时间/注册商 |
| `doh` | Google DoH | 线 | 回放解析状态 | DNS-over-HTTPS 查询 A/NS/status |
| `control` | 控制接口 `api.php` | 线 | 回放各轮 `download_link` | 采样 api.php 响应体解析 download_link |
| `payload` | 供包路径 | 包 | 回放各轮结构指纹 | `pefile`+`olefile` 静态解析 MSI/PE |

**混合模式**：每个采集器独立由环境变量 `LIEHU_<NAME>_MODE=mock|live` 切换，默认全 mock；
配置对应 API Key 后可单独切到 live，其余仍走 mock（详见 [`config.py`](../src/liehu/config.py)）。

### 4.2 数据处理分析模块（`src/liehu/analysis/`）

全部为**纯函数**，不触碰数据库，便于单测。

#### 4.2.1 去重归一化（[`dedup.py`](../src/liehu/analysis/dedup.py)）
- `normalize_domain()`：小写、去空白/末尾点、去 `www.` 前缀。
- `dedup_by_uuid()`：按 `task.uuid` 去重（吸收重叠窗与索引延迟）。
- `counts()`：同时给出**记录数 vs 站点数**两种口径。

#### 4.2.2 关联分析（[`correlation.py`](../src/liehu/analysis/correlation.py)）
- `classify_registration()`：多时钟分类 → `same_day` / `preexisting` / `reactivated`。
  关键判据：`首见.date < 注册.date` ⇒ reactivated（历史域名重注册）；注册日 == 基线 ⇒ same_day。
- `attribute_campaign()`：由**精确控制接口**映射战役标签。
- `confidence()`：连接件加权打分（`control_api`=5 / `analytics_id`=3 / `adjacent_reg`=2 / 共享项=1）；
  命中控制接口，或"分析 ID + 相邻注册"共现即 `confirmed`，否则 `candidate`。
- `detect_adjacent_registration()`：滑窗检测秒级注册批次（批处理痕迹）。
- `build_links()`：生成"壳→线→包"关系图边（requests/binds/returns/rotates）。
- `detect_route_topology()`：对比相邻轮采样识别 `ROUTE_MERGE` / `ROUTE_SPLIT`。

#### 4.2.3 稳定区哈希（[`stablehash.py`](../src/liehu/analysis/stablehash.py)）
- `stable_region_sha256(data, trim_tail=2)`：去掉不稳定末尾字节后的稳定区 SHA-256。
- `is_pure_rotation(prev, curr)`：完整哈希变、但稳定区/内嵌 PE/imphash/结构 ID 不变 ⇒ 纯轮换。
- `is_structural_change(prev, curr)`：稳定区、内嵌 PE、结构 ID、入口 RVA 或 **OLE 流数**在两次
  观测之间变化 ⇒ 结构换代。

> **实现修正**：早期版本 `is_structural_change` 误用 `prev.ole_identical != prev.ole_stream_count`
> （同一样本内 identical/total 比值，是数据属性而非变化信号），导致 22/25 的样本被恒判为结构换代。
> 已修正为比较两次观测间的 `ole_stream_count`，使 7·23 载荷正确输出**1 次结构换代 + 2 次尾字节轮换**，
> 与原文一致。该缺陷正是由单元测试 `test_pure_rotation_true_when_only_full_hash_changes` 暴露。

#### 4.2.4 差异引擎（[`diff.py`](../src/liehu/analysis/diff.py)）
纯函数 `diff_frontend` / `diff_control` / `diff_payload` / `diff_dns`，接收 `(prev, curr)`
返回事件列表。要点：
- 新前台 ⇒ `NEW_FRONTEND` + `FIRST_PUBLIC`。
- 载荷差异**结构换代优先于纯轮换**判断（更高优先级）。
- 控制端采集失败不算变化事件，交由 `errors` 账本。

### 4.3 追踪定位模块（`src/liehu/tracker.py` + `scheduler.py` + `alerting.py`）

- **tracker**：`run_frontend_cycle` / `run_control_cycle`（含路径拓扑检测 + 轮次推进）/
  `run_payload_cycle` / `run_dns_cycle` / `run_full_cycle`。负责调用采集 → 分析 → 落库 →
  `persist_event` / `_persist_links`。mock 轮次指针存于 `meta` 表。
- **scheduler**：APScheduler 分级调度（前台 300s / 控制 180s / DNS 600s / CT 1800s / 载荷 300s），
  `_safe` 包装保证单次失败不影响后续。
- **alerting**：`EVENT_PRIORITY` 事件→优先级映射，`EVENT_SINK` 事件→处置渠道映射，
  `build_diff_card()` 渲染差异卡（对象、首见/最近、上一状态、当前状态、事实、落点、证据链接）。

### 4.4 分级采集节奏（对应原文"值班流程"）

| 层 | 周期 | 依据 |
|----|------|------|
| 前台（壳） | 5 min（查最近 15 min 重叠窗） | 变化最快，需高频 + 去重 |
| 活跃控制端（线） | 3 min | 捕捉 download_link 合流/切换 |
| 载荷（包） | 5 min | 捕捉哈希轮换/结构换代 |
| DNS | 10 min | 生命周期状态 |
| CT / 注册 | 30 min | 较慢，作为"钟"交叉验证 |

---

## 5. API 设计（`src/liehu/routers/`）

所有读接口前缀 `/api`，直接查询 SQLite。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 总览水位：总数、战役/当天分类/题材分布、事件优先级、数据源模式、起点 IOC |
| GET | `/api/frontends?campaign&day_class&theme&limit` | 前台状态卡（壳），支持多维过滤 |
| GET | `/api/frontends/{domain}` | 单个前台详情 |
| GET | `/api/controls?control_api&limit` | 控制端采样列表 |
| GET | `/api/controls/timeline` | 按控制接口聚合的采样时间线 |
| GET | `/api/payloads?limit` | 载荷观测列表 |
| GET | `/api/payloads/compare` | 按 `structure_id` 归组的结构骨架对比 |
| GET | `/api/events?priority&event_type&limit` | 差异事件流（渲染为差异卡） |
| GET | `/api/errors?limit` | 采集错误账本 |
| GET | `/api/campaigns/graph?campaign` | 壳→线→包关系图（ECharts nodes+links+categories） |
| POST | `/api/campaigns/trigger` | 手动触发一次完整追踪周期 |
| GET | `/health` | 健康检查 |

应用装配见 [`main.py`](../src/liehu/main.py)：`lifespan` 启动时 `init_db()` → 若库为空自动
种子回放 → 按配置启动调度器；并静态托管 `web/` 仪表盘（`/` 首页 + `/assets`）。

---

## 6. Web 仪表盘（`src/liehu/web/`）

免构建静态方案：`index.html` + `assets/style.css` + `assets/app.js`（原生 JS + ECharts 5），
由 FastAPI 直接托管。六个标签页：

1. **总览水位**：统计卡 + 战役饼图 / 当天分类柱图 / 题材玫瑰图 / 事件优先级饼图 + 数据源模式与起点 IOC。
2. **前台（壳）**：按战役/当天分类/题材过滤的卡片网格。
3. **控制线（线）**：控制接口分时时间线，展示 download_link 从分离到合流、NXDOMAIN 标红。
4. **载荷（包）**：按 `structure_id` 归组的结构骨架对比表（MSI 大小、imphash、稳定区哈希、OLE、WiX）。
5. **关联图**：力导向图渲染"壳→线→包"连接件关系，可按战役过滤。
6. **事件流**：差异卡列表，按优先级着色/过滤。

顶栏提供"▶ 触发一轮追踪"按钮，调用 `POST /api/campaigns/trigger` 后刷新当前视图。

> 安全说明：仪表盘经 CDN 引入 ECharts；生产部署建议改为自托管并加 SRI，
> 且所有动态文本已通过 `esc()` HTML 转义防注入。

---

## 7. 测试与验证（`tests/`）

`pytest` 覆盖分析层纯函数与 API 集成：

| 测试文件 | 覆盖 |
|----------|------|
| `test_stablehash.py` | 稳定区哈希、纯轮换 vs 结构换代判定（含尾字节 006f/007f/008f 案例） |
| `test_correlation.py` | 多时钟分类、战役归因、连接件置信度、秒级注册批次、ROUTE_MERGE |
| `test_dedup.py` | 域名归一化、uuid 去重、记录数 vs 站点数 |
| `test_diff.py` | 前台/控制/载荷/DNS 差异事件（结构换代优先级） |
| `test_api_integration.py` | TestClient 验证 143 前台、noah=111/fezhx=32、关联图三层、优先级过滤、载荷骨架 |

**运行结果**：`34 passed`。

**种子回放验证**（`uv run python -m liehu.seed`）：
- 前台 143（noah 111 / fezhx 32）
- 差异事件 291：`NEW_FRONTEND` 143 + `FIRST_PUBLIC` 143 + `ROUTE_MERGE` 1 +
  `CONTROL_CHANGE` 1 + `PAYLOAD_STRUCTURAL_CHANGE` 1 + `PAYLOAD_ROTATION` 2
- 关系图边 290
- 与原文 7·23 水位一致。

---

## 8. 运行指南

```bash
# 1. 安装依赖（uv 自动创建 .venv 并按 uv.lock 还原）
uv sync

# 2. 生成/重放种子数据（复原 7·23 水位）
uv run python -m liehu.seed
#    分析逻辑变更后重置并重放：
uv run python scripts/reset_seed.py

# 3. 启动服务（首次为空库会自动种子）
uv run uvicorn liehu.main:app --host 127.0.0.1 --port 8010
#    打开 http://127.0.0.1:8010 查看仪表盘；/docs 查看 OpenAPI

# 4. 运行测试
uv run pytest -q

# 关闭后台调度器（仅看静态回放数据）：设置环境变量 LIEHU_SCHEDULER=0
# 切换某数据源到真实模式：设置 LIEHU_URLSCAN_MODE=live 并提供 URLSCAN_API_KEY
```

### 目录结构

```
chat-1/
├── pyproject.toml / uv.lock        # uv 项目与锁定依赖
├── src/liehu/
│   ├── config.py  db.py  models.py # 配置 / 数据层 / 领域模型
│   ├── mock/dataset.py             # 7·23 水位复原数据集
│   ├── collectors/                 # 采集层（6 采集器 + base + 工厂）
│   ├── analysis/                   # 分析层（dedup/correlation/stablehash/diff）
│   ├── tracker.py scheduler.py alerting.py  # 编排 / 调度 / 告警
│   ├── seed.py                     # 种子回放
│   ├── routers/                    # API 路由
│   ├── main.py                     # FastAPI 装配 + 静态托管
│   └── web/                        # 仪表盘（index.html + assets/）
├── tests/                          # pytest 单元 + 集成
├── scripts/                        # reset_seed 等运维脚本
└── docs/DESIGN.md                  # 本文档
```

---

## 9. 设计取舍与边界

- **战役标签仅为技术聚类**（基于连接件），不指向任何现实身份。
- **稳定区边界是经验值**：`trim_tail=2` 来自本批样本逐字节比较，换批样本边界可能落在
  PE overlay / 证书表之后，因此设为可配置参数。
- **mock 优先**：默认零外部依赖即可完整演示三层追踪；live 模式为真实接入预留抽象。
- **只读展示层**：仪表盘不做写操作（除手动触发周期），符合情报台"看板"定位。
- **防御用途**：本系统面向威胁情报追踪与防御处置，所有样本指纹均为静态元数据，不含可执行载荷。
