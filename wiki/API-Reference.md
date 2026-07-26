# API 参考

← 返回 [Wiki 首页](Home.md)

所有读接口前缀 `/api`（见 [`routers/__init__.py`](../src/liehu/routers/__init__.py)），直接查询 SQLite。
启动 `uvicorn liehu.main:app` 后可访问 `/docs` 查看自动生成的 OpenAPI 文档。

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 总览水位统计 |
| GET | `/api/frontends` | 前台状态卡列表（壳） |
| GET | `/api/frontends/{domain}` | 单个前台详情 |
| GET | `/api/controls` | 控制端采样列表（线） |
| GET | `/api/controls/timeline` | 按控制接口聚合的采样时间线 |
| GET | `/api/payloads` | 载荷观测列表（包） |
| GET | `/api/payloads/compare` | 按 `structure_id` 归组的结构骨架对比 |
| GET | `/api/events` | 差异事件流（渲染为差异卡） |
| GET | `/api/errors` | 采集错误账本 |
| GET | `/api/campaigns/graph` | 壳→线→包关系图（ECharts nodes+links+categories） |
| POST | `/api/campaigns/trigger` | 手动触发一次完整追踪周期 |
| GET | `/health` | 健康检查 |

---

## GET /api/stats

总览水位。无参数。返回：

```json
{
  "water_mark": "2026-07-23T19:36:43+08:00",
  "frontend_total": 143,
  "by_campaign": { "noah": 111, "fezhx": 32 },
  "by_dayclass": { "same_day": ..., "preexisting": ... },
  "by_theme": { "office": ..., "vpn": ... },
  "event_total": 291,
  "events_by_priority": { "high": ..., "pending": ..., "watch": ... },
  "error_total": 3,
  "modes": { "urlscan": "mock", "certspotter": "mock", "rdap": "mock",
             "doh": "mock", "control": "mock", "payload": "mock" },
  "starting_iocs": { ... }
}
```

`modes` 反映各采集器当前 mock/live 模式；`starting_iocs` 为追踪起点连接件。

## GET /api/frontends

前台状态卡（壳），支持多维过滤。

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `campaign` | string | — | 按战役过滤：noah/fezhx |
| `day_class` | string | — | 按当天分类过滤 |
| `theme` | string | — | 按题材过滤 |
| `limit` | int | 200 | 上限 1000 |

返回 `{ "count": n, "items": [ <frontends 行> ] }`，按 `last_seen` 倒序。

## GET /api/frontends/{domain}

按域名返回单条前台状态卡；不存在时返回 `{}`。

## GET /api/controls

控制接口分时采样。参数：`control_api`（按接口过滤）、`limit`（默认 200，上限 1000）。
返回 `{ "count": n, "items": [...] }`，按 `id` 倒序。

## GET /api/controls/timeline

无参数。返回按 `control_api` 聚合的时间线，供前端绘制 download_link 变化：

```json
{ "timeline": { "fezhx.com/api.php": [
    { "observed_at": "...", "download_link": "...", "http_status": 200, "error": null }
] } }
```

## GET /api/payloads

载荷观测记录列表。参数 `limit`（默认 200）。返回 `{ "count": n, "items": [...] }`，按 `id` 倒序。

## GET /api/payloads/compare

无参数。按 `structure_id` 归组，展示完整哈希轮换（同组多条）与结构换代（不同组）：

```json
{ "skeletons": [
  { "structure_id": "skeleton-9.1MB", "sample_count": 3,
    "msi_size": 9158656, "embedded_pe_size": ..., "pe_entry_rva": ...,
    "stable_sha256": "...", "imphash": "9b760feffec4fca9c313889f9a05ee36",
    "ole_stream_count": 25, "ole_identical": 25, "wix_version": "4.0.5.0",
    "full_hashes": ["...006f", "...007f", "...008f"] }
] }
```

## GET /api/events

差异事件流（只推变化），渲染为差异卡。

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `priority` | string | — | high/pending/watch |
| `event_type` | string | — | 按事件类型过滤 |
| `limit` | int | 200 | 上限 1000 |

返回 `{ "count": n, "items": [ <差异卡> ] }`，按 `id` 倒序。差异卡由
[`alerting.build_diff_card`](../src/liehu/alerting.py) 渲染，含对象、首见/最近、上一状态、当前状态、事实、落点、证据链接。

## GET /api/errors

采集错误账本。参数 `limit`（默认 200）。返回 `{ "count": n, "items": [...] }`。

## GET /api/campaigns/graph

壳→线→包关系图（ECharts 关系图友好结构）。参数 `campaign`（可选，按战役过滤）。

```json
{
  "categories": [ {"name": "壳-前台"}, {"name": "线-控制接口"},
                  {"name": "线-分析ID"}, {"name": "线-下载路径"}, {"name": "包-载荷骨架"} ],
  "nodes": [ { "id": "...", "name": "...", "category": 0,
               "node_type": "frontend", "campaign": "noah" } ],
  "links": [ { "source": "...", "target": "...", "relation": "requests", "campaign": "noah" } ]
}
```

`category` 序号对应节点类型（0=壳 / 1=控制 / 2=分析ID / 3=下载 / 4=包）。

## POST /api/campaigns/trigger

手动触发一次完整追踪周期（壳/线/包/DNS），调用 `tracker.run_full_cycle()`。
返回 `{ "status": "ok", "result": { ... } }`，`result` 含本轮新增事件等统计。

## GET /health

健康检查，返回服务存活状态（见 [`main.py`](../src/liehu/main.py)）。

---

延伸阅读：[数据模型](Data-Model.md) · [Web 仪表盘](Dashboard.md) · [系统架构](Architecture.md)
