# Web 仪表盘

← 返回 [Wiki 首页](Home.md)

免构建静态方案：[`web/index.html`](../src/liehu/web/index.html) +
[`assets/style.css`](../src/liehu/web/assets/style.css) +
[`assets/app.js`](../src/liehu/web/assets/app.js)（原生 HTML/CSS/JS + ECharts 5，CDN 引入），
由 FastAPI 通过 `main.py` 的 `lifespan` 直接静态托管（`/` 首页 + `/assets`）。

启动服务后打开 <http://127.0.0.1:8010> 即可访问，暗色情报台风格，无需任何前端构建步骤。

## 六个标签页

| 标签页 | 层 | 内容 |
|--------|----|------|
| **总览水位** | — | 统计卡（前台总数/noah/fezhx/事件总数…）+ 战役饼图 / 当天分类柱图 / 题材玫瑰图 / 事件优先级饼图 + 数据源模式与起点 IOC |
| **前台（壳）** | 壳 | 按战役 / 当天分类 / 题材过滤的卡片网格 |
| **控制线（线）** | 线 | 控制接口分时时间线，展示 download_link 从分离到合流、NXDOMAIN 标红 |
| **载荷（包）** | 包 | 按 `structure_id` 归组的结构骨架对比表（MSI 大小、imphash、稳定区哈希、OLE、WiX） |
| **关联图** | 关联 | 力导向图渲染"壳→线→包"连接件关系，可按战役过滤 |
| **事件流** | — | 差异卡列表，按优先级着色 / 过滤 |

## 顶栏

- **水位显示**：右上角显示当前观测水位时间（`水位 2026-07-23T19:36:43+08:00`），
  由 `/api/stats` 的 `water_mark` 提供；深链进入非总览标签时也会独立补齐。
- **▶ 触发一轮追踪**：调用 `POST /api/campaigns/trigger` 执行一次完整追踪周期，
  完成后 toast 提示新增事件数并刷新当前视图。

## 标签页深链（#hash）

标签页支持 URL hash 深链，可收藏 / 分享 / 自动化：

```
http://127.0.0.1:8010/#overview   总览水位（缺省）
http://127.0.0.1:8010/#frontends  前台
http://127.0.0.1:8010/#controls   控制线
http://127.0.0.1:8010/#payloads   载荷
http://127.0.0.1:8010/#graph      关联图
http://127.0.0.1:8010/#events     事件流
```

`app.js` 启动时读取 `location.hash` 激活对应标签；首次进入才触发该标签的数据加载
（懒加载），切回时刷新 ECharts 图表尺寸。

## 前端实现要点

- **`fetchJSON()`**：统一封装 `/api` 请求。
- **`esc()`**：所有动态文本经 HTML 转义防注入。
- **`makeChart()`**：ECharts `init(el, "dark")`，标签页切换后 `resize()`。
- **关联图**：ECharts `type: "graph"` + `layout: "force"`，节点按 `node_type` 分 size/color。

## 安全说明

仪表盘经 CDN 引入 ECharts；**生产部署建议改为自托管并添加 SRI 完整性校验**。
所有动态文本已通过 `esc()` HTML 转义防注入。仪表盘为**只读看板**（除手动触发周期外不做写操作）。

---

延伸阅读：[API 参考](API-Reference.md) · [快速开始](Getting-Started.md) · [测试与验证](Testing-and-Verification.md)
