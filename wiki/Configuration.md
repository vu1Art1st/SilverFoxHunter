# 配置指南

← 返回 [Wiki 首页](Home.md)

全部配置集中在 [`src/liehu/config.py`](../src/liehu/config.py) 的 `Settings` 单例，
通过**环境变量**覆盖默认值。核心思路：**默认全 mock 零外部依赖即可完整演示**，
配置对应 API Key 后可将**单个采集器**切到 live，其余仍走 mock（混合模式）。

## 环境变量总表

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `LIEHU_SCHEDULER` | `true` | 是否在启动时运行后台调度器；设 `0`/`false` 只看静态回放数据 |
| `LIEHU_URLSCAN_MODE` | `mock` | urlscan 采集器模式：`mock`/`live` |
| `LIEHU_CERTSPOTTER_MODE` | `mock` | certspotter 模式 |
| `LIEHU_RDAP_MODE` | `mock` | rdap 模式 |
| `LIEHU_DOH_MODE` | `mock` | doh 模式 |
| `LIEHU_CONTROL_MODE` | `mock` | control 模式 |
| `LIEHU_PAYLOAD_MODE` | `mock` | payload 模式 |
| `URLSCAN_API_KEY` | — | urlscan live 模式所需 API Key |
| `CERTSPOTTER_API_KEY` | — | certspotter live 模式所需 API Key |

> 布尔量识别 `1/true/yes/on`（不区分大小写）为真。

## 混合模式（mock ⇄ live）

每个采集器由独立环境变量切换，互不影响。例如只把 urlscan 接真实源、其余保持回放：

```powershell
# PowerShell
$env:LIEHU_URLSCAN_MODE="live"
$env:URLSCAN_API_KEY="<your-key>"
uv run uvicorn liehu.main:app --host 127.0.0.1 --port 8010
```

`rdap` / `doh` / `control` / `payload` 的 live 模式不需要 API Key（公共接口或直连解析），
`urlscan` / `certspotter` 需要。各采集器 live 行为见 [系统架构 · Provider 抽象](Architecture.md#采集层provider-抽象)。

## 采集节奏（Cadence）

`config.py::Cadence` 定义分级采集节奏（秒），对应文章"值班流程"：

| 字段 | 默认 | 层 |
|------|------|----|
| `frontend_seconds` | 300 | 前台（壳），查最近 `frontend_window_minutes`=15 分钟重叠窗 |
| `control_seconds` | 180 | 活动控制端（线） |
| `payload_seconds` | 300 | 供包路径静态解析（包） |
| `dns_seconds` | 600 | DNS 生命周期 |
| `ct_seconds` | 1800 | CT / 注册数据（较慢，作为"钟"交叉验证） |

节奏当前为代码内默认值；如需调整可修改 `Cadence` 默认或在实例化 `Settings` 时覆盖。

## 路径与存储

| 项 | 默认位置 | 说明 |
|----|----------|------|
| 数据库 | `data/liehu.db` | SQLite + WAL，启动自动建目录 |
| 证据落盘 | `data/evidence/` | 采集原始响应 |
| 仪表盘静态资源 | `src/liehu/web/` | `WEB_DIR`，FastAPI 静态托管 |

## 追踪起点连接件

`Settings.seed_control_domains` 内置文章 7·23 晚间水位的已知活动控制接口，作为追踪起点：

```python
seed_control_domains = ("noah-admin.site", "fezhx.com")
```

---

延伸阅读：[快速开始](Getting-Started.md) · [系统架构](Architecture.md) · [API 参考](API-Reference.md)
