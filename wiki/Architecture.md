# 系统架构

← 返回 [Wiki 首页](Home.md)

## 分层总览

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

## 各层职责

| 层 | 模块 | 职责 |
|----|------|------|
| 采集层 | `collectors/` | 把外部数据源抽象为统一 `Provider`，每个采集器支持 `mock` / `live` 双模式；原始响应落盘 `data/evidence/`，失败写入 `errors` 账本。 |
| 分析层 | `analysis/` | **纯函数**实现，不直接读写数据库，便于单测。承担去重、多时钟分类、连接件归因、稳定区哈希、差异计算。 |
| 编排层 | `tracker.py` | 把"采集 → 分析 → 落库 → 生成事件"串成一次"追踪周期"。 |
| 调度层 | `scheduler.py` | 用 APScheduler 按不同层级的节奏分级触发周期。 |
| 告警层 | `alerting.py` | 为事件分配优先级、映射处置渠道、渲染差异卡。 |
| 展示层 | `routers/` + `main.py` | FastAPI 只读接口 + 静态仪表盘托管。 |

## 采集层：Provider 抽象

统一基类 `collectors/base.py::Provider` 提供 `mode` / `api_key` / `is_live` 属性、
证据落盘 `dump_evidence()`、错误记账 `record_error()` 与 `sha256_hex()` 等工具。
`build_collectors()` 工厂按配置组装全部采集器。

| 采集器 | 数据源 | 层 | mock 行为 | live 行为 |
|--------|--------|----|-----------|-----------|
| `urlscan` | URLScan Search API | 壳 | 从 mock 数据集筛选前台 | 构造 `filename.keyword` / `page.domain` 精确查询 + 重叠时间窗 |
| `certspotter` | CertSpotter CT 日志 | 线 | 回放 CT 首见 | 拉取子域证书 |
| `rdap` | RDAP / WHOIS | 线 | 回放注册时间 | 查询注册时间 / 注册商 |
| `doh` | Google DoH | 线 | 回放解析状态 | DNS-over-HTTPS 查询 A/NS/status |
| `control` | 控制接口 `api.php` | 线 | 回放各轮 `download_link` | 采样 api.php 响应体解析 download_link |
| `payload` | 供包路径 | 包 | 回放各轮结构指纹 | `pefile` + `olefile` 静态解析 MSI/PE |

## 编排层：一次追踪周期

`tracker.py` 提供分周期入口：

- `run_frontend_cycle` —— 采集前台（壳），去重后 upsert，产出 `NEW_FRONTEND` / `FIRST_PUBLIC`。
- `run_control_cycle` —— 采样控制接口（线），检测路径拓扑（`ROUTE_MERGE` / `ROUTE_SPLIT`）并推进 mock 轮次。
- `run_payload_cycle` —— 静态解析载荷（包），区分纯轮换与结构换代。
- `run_dns_cycle` —— DNS 生命周期状态。
- `run_full_cycle` —— 依次执行上述全部（`POST /api/campaigns/trigger` 调用它）。

每个周期内：调用采集 → 分析（纯函数）→ 落库 → `persist_event` / `_persist_links`。
mock 轮次指针存于 `meta` 表，保证多次触发按序推进复原时间线。

## 分级调度节奏

`scheduler.py` 用 APScheduler（BackgroundScheduler）分级调度，`_safe` 包装保证单次失败不影响后续：

| 层 | 周期 | 依据 |
|----|------|------|
| 前台（壳） | 300s | 变化最快，需高频 + 去重（查最近 15 分钟重叠窗） |
| 活跃控制端（线） | 180s | 捕捉 download_link 合流 / 切换 |
| 载荷（包） | 300s | 捕捉哈希轮换 / 结构换代 |
| DNS | 600s | 生命周期状态 |
| CT / 注册 | 1800s | 较慢，作为"钟"交叉验证 |

节奏配置见 `config.py::Cadence`；`LIEHU_SCHEDULER=0` 可整体关闭调度器。

## 应用装配

`main.py` 的 `lifespan`：启动时 `init_db()` → 若库为空自动种子回放 → 按配置启动调度器；
并静态托管 `web/` 仪表盘（`/` 首页 + `/assets`）。

---

延伸阅读：[数据模型](Data-Model.md) · [API 参考](API-Reference.md) · [配置指南](Configuration.md)
