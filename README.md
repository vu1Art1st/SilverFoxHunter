# SilverFoxHunter · 银狐猎手

> 银狐（SilverFox）仿冒下载链威胁情报追踪系统
> 基于文章《我是怎么追踪银狐新域名的》的 **"壳 / 线 / 包"三层方法论** 实现。
>
> 仓库地址：https://github.com/vu1Art1st/SilverFoxHunter

银狐团伙通过大量**仿冒下载页面**（伪装成物流查询、Apple Music、办公软件、券商、VPN、AI 工具等）
诱导受害者下载木马，这些前台域名**当天现做现用、更换极快**，单纯封域名收效甚微。

本系统不盯着变化最快的那一层，而是沿着 **壳 → 线 → 包** 从易变到持久逐层下沉，
抓住相对稳定的"连接件"来关联与追踪，并以**差异事件流**的形式只推送有意义的变化。

- **壳（Shell / 前台）**：仿冒页面域名、题材、标题 —— 变化最快。
- **线（Line / 控制线）**：控制接口 `api.php`、`download_link`、分析 ID、下载路径 —— 跨壳复用。
- **包（Package / 载荷）**：MSI / 内嵌 PE；完整哈希秒级轮换，但**结构骨架**持久。

> ⚠️ 说明：本系统面向**威胁情报追踪与防御处置**。战役标签仅为基于连接件的技术聚类，
> 不指向任何现实身份；内置样本指纹均为**静态元数据**，不含可执行载荷。默认零外部依赖的
> **mock 模式**即可完整演示三层追踪。

---

## ✨ 功能特性

- **三层追踪**：壳/线/包分层建模，逐层下沉锁定稳定连接件。
- **多时钟关联**：CT（CertSpotter）、RDAP/WHOIS、DNS（DoH）、URLScan 四源交叉判断域名真实"年龄"与用途。
- **连接件归因**：控制接口 / 分析 ID / 秒级注册 / 共享项加权打分，多强连接件同时命中才确认关联。
- **稳定区哈希**：去尾字节 SHA-256 + imphash + 内嵌 PE + OLE 结构，锁定生产骨架，区分"纯轮换"与"结构换代"。
- **差异事件流**：只推变化，按 `high / pending / watch` 分级并落到不同处置渠道。
- **Web 仪表盘**：六个标签页（总览水位 / 前台 / 控制线 / 载荷 / 关联图 / 事件流），免构建静态托管。
- **登录鉴权**：内置单管理员账户，所有页面需登录后访问（仅标准库 pbkdf2 + hmac 签名 Cookie，零新增依赖）。
- **个人中心**：可修改用户名 / 密码 / 头像，并通过“⚙ 配置”在线设置各采集器模式与 API 密钥。
- **混合数据源**：每个采集器可独立在 `mock`（回放）/ `live`（真实源）间切换。

---

## 🚀 快速开始

前置：安装 [uv](https://docs.astral.sh/uv/)（Python 环境与依赖管理工具），Python ≥ 3.10。

```bash
# 0. 克隆仓库
git clone https://github.com/vu1Art1st/SilverFoxHunter.git
cd SilverFoxHunter

# 1. 安装依赖（uv 自动创建 .venv 并按 uv.lock 还原）
uv sync

# 2. 启动服务（首次为空库会自动种子回放, 复原 7·23 水位, 并创建默认管理员 admin/admin）
uv run uvicorn liehu.main:app --host 127.0.0.1 --port 8010

# 3. 浏览器打开仪表盘
#    http://127.0.0.1:8010        —— Web 仪表盘（未登录自动跳转 /login）
#    http://127.0.0.1:8010/docs   —— OpenAPI 交互文档
#    默认账户：admin / admin（登录后请在个人中心修改）
```

> Windows PowerShell 设置环境变量用 `$env:NAME="value"`，例如：
> `$env:LIEHU_SCHEDULER="0"; uv run uvicorn liehu.main:app --port 8010`

### 常用操作

```bash
# 只看静态回放数据、关闭后台分级调度器
$env:LIEHU_SCHEDULER="0"; uv run uvicorn liehu.main:app --port 8010

# 重新生成/重放种子数据（复原 7·23 水位）
uv run python -m liehu.seed

# 分析逻辑变更后, 清空并重放种子（让持久化的事件/分类反映最新算法）
uv run python scripts/reset_seed.py

# 运行测试
uv run pytest -q
```

---

## 🖥️ 仪表盘导览

| 标签页 | 深链 | 内容 |
|--------|------|------|
| 总览水位 | `#overview` | 统计卡 + 战役 / 当天分类 / 题材 / 事件优先级图表 + 数据源模式与起点 IOC |
| 前台 · 壳 | `#frontends` | 按战役 / 当天分类 / 题材过滤的前台卡片网格 |
| 控制线 · 线 | `#controls` | 控制接口分时时间线（download_link 从分离到合流、NXDOMAIN 标红） |
| 载荷 · 包 | `#payloads` | 按 `structure_id` 归组的结构骨架对比（MSI 大小 / imphash / 稳定区哈希 / OLE / WiX） |
| 关联图 | `#graph` | 力导向渲染"壳→线→包"连接件关系，可按战役过滤 |
| 事件流 | `#events` | 差异卡列表，按优先级着色 / 过滤 |

顶栏"▶ 触发一轮追踪"按钮调用 `POST /api/campaigns/trigger` 手动执行一次完整追踪周期。
顶栏右侧头像入口进入**个人中心**（`/profile`），可改用户名 / 密码 / 头像并配置 API 密钥。
标签页支持 `#hash` 深链，可直接收藏 / 分享，例如 `http://127.0.0.1:8010/#graph`。
未登录访问任何页面均会自动重定向到 `/login`。

---

## 🔌 API 一览

所有读接口前缀 `/api`，直接查询 SQLite。完整 schema 见 `/docs`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 总览水位：总数、战役/当天分类/题材分布、事件优先级、数据源模式、起点 IOC |
| GET | `/api/frontends` | 前台状态卡（壳），支持 `campaign` / `day_class` / `theme` / `limit` 过滤 |
| GET | `/api/frontends/{domain}` | 单个前台详情 |
| GET | `/api/controls` | 控制端采样列表，支持 `control_api` / `limit` |
| GET | `/api/controls/timeline` | 按控制接口聚合的采样时间线 |
| GET | `/api/payloads` | 载荷观测列表 |
| GET | `/api/payloads/compare` | 按 `structure_id` 归组的结构骨架对比 |
| GET | `/api/events` | 差异事件流（渲染为差异卡），支持 `priority` / `event_type` / `limit` |
| GET | `/api/errors` | 采集错误账本 |
| GET | `/api/campaigns/graph` | 壳→线→包关系图（ECharts nodes+links+categories），支持 `campaign` |
| POST | `/api/campaigns/trigger` | 手动触发一次完整追踪周期 |
| POST | `/api/auth/login` | 登录（用户名/密码），成功下发签名会话 Cookie |
| POST | `/api/auth/logout` | 登出，清除会话 Cookie |
| GET | `/api/auth/me` | 当前登录用户（未登录返回 401） |
| GET | `/api/profile` | 个人资料（用户名 + 头像） |
| PUT | `/api/profile/username` · `/password` · `/avatar` | 修改用户名 / 密码 / 头像 |
| GET/PUT | `/api/settings/apikeys` | 查看（掩码）/ 保存采集器模式与 API 密钥 |
| GET | `/health` | 健康检查 |

> 除 `/api/auth/login`、`/health` 外, 所有业务接口均需携带有效会话 Cookie, 否则返回 401。

---

## ⚙️ 配置（环境变量）

| 变量 | 默认 | 说明 |
|------|------|------|
| `LIEHU_SCHEDULER` | `1` | 是否在启动时运行后台分级调度器（`0` 关闭，仅看静态回放） |
| `LIEHU_URLSCAN_MODE` | `mock` | URLScan 采集器模式 `mock` / `live` |
| `LIEHU_CERTSPOTTER_MODE` | `mock` | CertSpotter 采集器模式 |
| `LIEHU_RDAP_MODE` | `mock` | RDAP/WHOIS 采集器模式 |
| `LIEHU_DOH_MODE` | `mock` | DNS（DoH）采集器模式 |
| `LIEHU_CONTROL_MODE` | `mock` | 控制接口采集器模式 |
| `LIEHU_PAYLOAD_MODE` | `mock` | 载荷解析采集器模式 |
| `URLSCAN_API_KEY` | — | URLScan live 模式所需 API Key（亦可在个人中心在线配置） |
| `CERTSPOTTER_API_KEY` | — | CertSpotter live 模式所需 API Key（亦可在个人中心在线配置） |
| `LIEHU_SECRET` | — | 会话签名密钥；缺省时自动生成并持久化到数据库 |

**混合模式**：默认全 mock（零外部依赖）；可单独将某采集器切到 live 并提供对应 API Key，其余仍走 mock。例如：

```bash
$env:LIEHU_URLSCAN_MODE="live"; $env:URLSCAN_API_KEY="<your-key>"; uv run uvicorn liehu.main:app --port 8010
```

> 除环境变量外，登录后也可在**个人中心 → ⚙ 配置**中在线修改各采集器模式与 API 密钥；在线配置持久化在数据库，并在保存后即时生效、重启后仍生效（优先级高于环境变量默认值）。

分级采集节奏（前台 300s / 控制 180s / DNS 600s / CT 1800s / 载荷 300s）见 [`config.py`](src/liehu/config.py)。

---

## 🗂️ 项目结构

```
SilverFoxHunter/
├── pyproject.toml / uv.lock        # uv 项目与锁定依赖
├── README.md                       # 本文件
├── src/liehu/
│   ├── config.py  db.py  models.py # 配置 / 数据层 / 领域模型
│   ├── auth.py                      # 鉴权（密码哈希 / 签名会话 / 默认管理员）
│   ├── mock/dataset.py             # 7·23 水位复原数据集
│   ├── collectors/                 # 采集层（6 采集器 + base + 工厂）
│   ├── analysis/                   # 分析层（dedup / correlation / stablehash / diff, 纯函数）
│   ├── tracker.py scheduler.py alerting.py  # 编排 / 调度 / 告警
│   ├── seed.py                     # 种子回放
│   ├── routers/                    # API 路由（含 auth / account）
│   ├── main.py                     # FastAPI 装配 + 静态托管 + 页面守卫
│   └── web/                        # 仪表盘（index/login/profile.html + assets/）
├── tests/                          # pytest 单元 + 集成（含鉴权）
├── scripts/reset_seed.py           # 清空并重放种子的运维脚本
├── docs/DESIGN.md                  # 系统设计文档
└── wiki/                           # 项目 Wiki（见下）
```

---

## 🧪 测试与验证

```bash
uv run pytest -q      # 41 passed
```

覆盖分析层纯函数（去重 / 多时钟分类 / 连接件置信度 / 稳定区哈希 / 差异引擎）、
API 集成（TestClient 验证 143 前台、noah=111 / fezhx=32、关联图三层、优先级过滤、载荷骨架）
与鉴权（登录成功/失败、未授权 401、页面守卫重定向、改密码后旧密码失效、API 密钥掩码）。

**复原的 7·23 水位**：143 前台（noah 111 / fezhx 32）、291 差异事件
（`NEW_FRONTEND` 143 + `FIRST_PUBLIC` 143 + `ROUTE_MERGE` 1 + `CONTROL_CHANGE` 1 +
`PAYLOAD_STRUCTURAL_CHANGE` 1 + `PAYLOAD_ROTATION` 2）、关系图边 290，与原文一致。

---

## 📚 文档

- **[项目 Wiki](wiki/Home.md)** —— 方法论、架构、数据模型、API、仪表盘、配置、测试的完整导航。
- **[系统设计文档](docs/DESIGN.md)** —— 详尽的分层设计与取舍说明。

---

## 🛠️ 技术栈

Python ≥ 3.10 · FastAPI + uvicorn · APScheduler · httpx · pefile + olefile ·
SQLite（标准库 + WAL）· 原生 HTML/CSS/JS + ECharts 5（CDN，免构建）· pytest · uv 管理。
