# 猎狐系统（Fox Hunting System）实现计划

## 摘要
将文章《我是怎么追踪银狐新域名的》所述的人工追踪管道自动化。核心是"壳(Shell)/线(Line)/包(Package)"三层模型 + 多时钟关联 + 连接件归因 + 只推变化的差异告警。技术栈：后端 Python 3.11 + FastAPI + SQLite + APScheduler + httpx；前端 React + Vite + TS + ECharts（关联图/时间线）。混合数据模式：默认使用从文章 7·23 水位复原的模拟数据源，配置 API Key 后切换真实源。

## 第一部分：文章技术思想总结（写入 docs/DESIGN.md）
- **三层模型对照**：壳（域名/标题/品牌/模板，变化最快）→ 保存精确控制接口、分析ID、秒级注册差、模板残留；线（控制域/api.php/download_link/下载路径，较持久）→ 保存响应体哈希、download_link、分时采样；包（完整哈希秒级轮换，但 MSI/OLE 流、内嵌PE、imphash、稳定区哈希更持久）。
- **核心方法**：从已确认连接件（api.php / 分析ID / 下载路径）出发"守旧线等新壳"；URLScan 请求关系发现新前台；多时钟（CT/RDAP/DNS/URLScan）区分"现做现用"与"提前备货"；连接件归因（精确API+分析ID+秒级注册+相邻IP 多项共现才入关联集）；稳定区哈希（去尾字节求持久载荷身份）；只推变化的差异卡告警。
- **事件模型**：NEW_FRONTEND、CONTENT_CHANGE、CONTROL_CHANGE、ROUTE_MERGE/SPLIT、PAYLOAD_ROTATION、PAYLOAD_STRUCTURAL_CHANGE、STATUS_CHANGE 及优先级分级。

## 第二部分：系统技术架构
分层：采集层（Collectors，Provider 抽象=Mock+Live）→ 处理分析层（去重/归一化、多时钟关联、连接件归因、稳定区哈希、差异引擎）→ 状态存储层（SQLite + 原始证据落盘）→ 调度层（分级节奏定时任务）→ 告警层（差异卡+优先级）→ API/前端展示层。

## 第三部分：后端实现（backend/）
- **基础设施**：`app/config.py`（mock/live 开关、API Key、分级采集节奏）、`app/db.py`（SQLite 引擎/会话）、`app/models.py`（Frontend、ControlSample、DnsSnapshot、Payload、Event、ErrorLog、Campaign）、`app/schemas.py`。
- **采集层 `app/collectors/`**：`base.py`（Provider 抽象）、`urlscan.py`（壳：请求关系发现前台，重叠时间窗+UUID去重查询）、`certspotter.py`（CT时间线）、`rdap.py`（注册时间）、`doh.py`（DNS 状态与 Status 判定）、`control.py`（线：分时采样 api.php，保存响应头/体SHA256/download_link）、`payload.py`（包：zipfile/olefile/pefile 静态解析，缺库时降级用模拟结构指标）。
- **模拟数据源 `app/mock/dataset.py`**：复原文章 7·23 水位（noah 111/fezhx 32、四物流前台、Apple Music 四站、gnrrn 下载路径、MSI 9.1MB→6.9MB 换代、去尾两字节稳定哈希、imphash 等），供 Mock Provider 分时"回放"以驱动完整流程与差异事件。
- **处理分析 `app/analysis/`**：`dedup.py`（UUID去重+page.domain 归一化）、`correlation.py`（多时钟分类 + 连接件归因聚类为 noah/fezhx 战役）、`stablehash.py`（去尾字节稳定区哈希）、`diff.py`（对比上一状态生成事件）。
- **调度与告警**：`app/scheduler.py`（APScheduler：前台5-10min/15min窗、控制端3-5min、CT/RDAP/DNS 按生命周期）、`app/alerting.py`（差异卡生成+优先级：高优=精确接口/下载路径/结构换代）。
- **API `app/routers/`**：frontends、controls、payloads、events、campaigns、stats（水位统计），及手动触发扫描端点；`app/main.py` 挂载路由+启动调度器；`requirements.txt`；`seed.py`（用模拟数据集初始化 DB）。

## 第四部分：前端仪表盘（frontend/，React+Vite+TS）
- **总览页**：水位卡（前台总数/去重数、noah vs fezhx、当天现做/库存/复扫/内容变化分类）。
- **前台列表页**：每域名状态卡（首次/最近记录、当前标题、IP、HTTP状态、控制接口、分析ID、证据链接）。
- **控制线页**：api.php 分时采样时间线 + download_link 变化 + ROUTE_MERGE 可视化。
- **载荷页**：MSI/PE 结构换代对比表（大小、入口RVA、稳定区SHA256、imphash、OLE流一致数）。
- **战役关联图页**：ECharts 关系图展示 壳→线→包 连接件（域名/api.php/分析ID/下载路径/样本）。
- **事件流页**：差异卡按优先级过滤；`src/api.ts` 封装后端调用。

## 第五部分：文档（docs/DESIGN.md）
系统设计文档：文章技术总结、架构图（mermaid）、三层数据模型与表结构、采集/关联/差异算法说明、mock↔live 切换方式、运行步骤、事件与告警口径、防御用途与免责声明（对齐文章"银狐关联"为战役标签、不指向现实身份）。

## 测试计划
- 后端：pytest 覆盖 dedup（UUID去重）、correlation（连接件归因分类）、stablehash（去尾字节稳定哈希）、diff（各事件类型触发）。
- 集成：运行 seed.py + 启动服务，验证 /stats 返回 143 前台水位、Mock 分时回放触发 ROUTE_MERGE 与 PAYLOAD_STRUCTURAL_CHANGE。
- 前端：`npm run build` 通过；仪表盘各页正常渲染并拉取数据。

## 假设
- 猎狐系统定位为防御性威胁情报追踪工具（对齐文章防御复盘性质）。
- 默认 Mock 模式无需任何密钥即可完整运行；Live 模式需用户自备 URLScan/CertSpotter API Key。
- 前端与后端分离，开发期 Vite 代理到 FastAPI；提供一键运行说明。