# 更新日志 · Changelog

本文件记录 **SilverFoxHunter · 银狐猎手** 的每次版本更新。

- 格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
- 版本号遵循 [语义化版本 SemVer](https://semver.org/lang/zh-CN/) `主版本.次版本.修订号`（`x.y.z`）。
- 当前处于 **0.y.z 早期开发阶段**，公共接口与数据结构可能随时调整；待功能与稳定性达到发布标准后再进入 `1.0.0`。

变更类型：`新增(Added)` / `变更(Changed)` / `修复(Fixed)` / `移除(Removed)` / `安全(Security)`。

---

## [未发布 Unreleased]

自 `v0.3.0` 以来尚未打标签的改动，将在下一个版本汇总发布。

### 新增
- 微步在线（ThreatBook）情报采集器与 API 路由，为仿冒站点补充恶意/团伙情报。
- 情报库模块：跨同作者 16 篇威胁猎人手记归一化的 IOC 目录（P1/P2/P3 优先级 + `block` / 仅聚类不封禁 处置分类）与来源 / 方法学时间线。
- 控制面继承（CONTROL_TAKEOVER）、下载端点迁移（DOWNLOAD_MIGRATION）、死链投递（DEAD_LINK_DELIVERY）三类差异事件接入「事件流」与「关联图」（新增 `succeeds` / `migrates_to` 关系边）。
- 事件流支持按事件类型筛选。
- 仿冒站点**列表视图**（卡片/列表切换）与**点击域名弹出站点截图**能力；站点无法访问时标注「域名疑似失效 / 访问异常」。
- 仿冒站点数据 **CSV 导出**（UTF-8 BOM + CRLF，全字段中文表头，兼容 Excel/WPS）。
- 配置页新增各数据源官方**密钥申请与 API 文档链接**及认证方式说明。

### 变更
- 情报库标签页以 **IOC 目录**为主内容，情报来源 / 方法学时间线降级为默认折叠的可展开条带。
- 仪表盘术语专业化：仿冒站点集群归属（noah / fezhx C2 域名扩线关联）、C2 控制端、恶意载荷、域名注册时效分类、社工诱饵题材分布等。
- 校准 CertSpotter 采集器以对齐 SSLMate CT Search API v1（`Authorization: Bearer` 令牌认证、`after` 游标分页、`expand` 参数）；补充 URLScan `API-Key` 认证规范。

---

## [0.3.0] - 2026-07-27

Web 仪表盘、测试与文档 —— 首个可完整演示的端到端版本。

### 新增
- 仪表盘单页应用外壳与登录后业务逻辑（原生 JS + ECharts，暗色情报台风格）。
- 登录页与个人中心 / API 密钥设置页。
- 仪表盘、登录、个人中心样式。
- 分析层单元测试（stablehash / dedup / correlation / diff）与 API、鉴权集成测试（共享夹具）。
- 架构与方法论设计文档、项目 Wiki、README、仪表盘截图与设计规格文档。

## [0.2.0] - 2026-07-27

后端 API 与鉴权层 —— 对外提供受保护的数据服务。

### 新增
- PBKDF2 口令哈希与签名会话 Cookie 鉴权。
- 业务 API：水位统计、前台（壳）、控制线（线）、差异事件、载荷（包）、战役关联图。
- 登录 / 登出 / 会话接口，个人中心与 API 密钥设置接口。
- FastAPI 应用装配、页面路由与 Cookie 守卫；所有业务路由统一挂载登录鉴权。

## [0.1.0] - 2026-07-27

核心引擎 —— 采集、分析与追踪底座。

### 新增
- 项目脚手架：`.gitignore`、Python 版本锁定、项目元数据与 uv 锁文件。
- 应用配置、核心领域数据模型、SQLite Schema（用户与应用设置表）。
- 内置演示数据集与种子回放 / 重置脚本。
- 采集器：基类接口、URLScan、CertSpotter、RDAP、DoH、控制面、载荷。
- 分析层：稳定结构哈希、前台去重、壳/线/包关联图、载荷代际差异。
- 追踪编排流水线、高优先级事件告警、后台采集调度器。

---

[未发布 Unreleased]: https://github.com/vu1Art1st/SilverFoxHunter/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/vu1Art1st/SilverFoxHunter/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/vu1Art1st/SilverFoxHunter/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vu1Art1st/SilverFoxHunter/releases/tag/v0.1.0
