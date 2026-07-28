# 微步在线 (ThreatBook) API 集成调研与方案设计

> 任务: 为 SilverFoxHunter 设计"仿冒站点 ↔ 微步威胁情报"联动查询功能。
> 调研时间: 2026-07-27 · 依据: 微步在线云 API 官方文档 (x.threatbook.com/apiDocs)

## 1. 背景与目标

系统当前追踪的三层对象都适合用微步情报做交叉印证:

| 系统对象 | 数量 (当前水位) | 联动价值 |
| --- | --- | --- |
| 仿冒站点域名 (frontends) | 143 | 验证钓鱼/仿冒判定、发现团伙标签 |
| C2 控制域名 (noah-admin.site 等) | 3 | 确认 C2 判定、关联安全事件 |
| 载荷下载宿主 (360down.net 等) | 2 | 确认恶意软件分发判定、关联样本 |

目标: 让分析师在仪表盘内直接看到每个域名的微步威胁判定 (恶意/可信度/威胁类型/团伙标签)，并可按需下钻查看完整情报上下文。

## 2. 候选接口调研

### 2.1 失陷检测接口 (批量模式)

- **端点**: `GET/POST https://api.threatbook.cn/v3/scene/dns` (或 `/v3/scene/ioc`)
- **批量能力**: `resource` 参数支持逗号分隔, **单次最多 100 个域名/IP**
- **请求参数**: `apikey` / `resource` / `lang` (zh/en) / `realtime_verdict` (是否剔除过期情报)
- **响应核心字段** (每个域名):
  - `is_malicious`: 是否恶意 (bool)
  - `confidence_level`: 可信度 low/medium/high
  - `severity`: 严重级别 critical/high/medium/low/info
  - `judgments`: 威胁类型数组 (C2 / Malware / MiningPool / Whitelist …)
  - `tags_classes`: 团伙/家族/安全事件标签 (如 "银狐" 团伙标签)
  - `permalink`: X 情报中心详情页链接
- **定位**: 出站失陷检测场景, 只检出 C2 / 恶意软件 / 矿池等出站威胁, **轻量判定, 无 whois/样本等上下文**

### 2.2 域名分析接口 (单个详细模式)

- **端点**: `GET/POST https://api.threatbook.cn/v3/domain/query`
- **批量能力**: **仅支持单个域名查询**
- **请求参数**: `apikey` / `resource` / `exclude` (裁剪响应字段, 逗号分隔) / `lang`
- **响应核心字段**: 除 2.1 的判定字段外, 额外提供完整上下文:
  - `intelligences`: 情报来源明细 (微步实验室/X 奖励计划/开源情报, 含发现时间、可信度、过期状态)
  - `samples`: 关联恶意样本 (最多 20 条, sha256/检出率/家族)
  - `cur_ips`: 当前解析 IP (含运营商/地理位置)
  - `cur_whois`: 当前 Whois (注册商/注册者/邮箱/注册时间)
  - `cas`: SSL 证书信息 (与 crt.sh CT 时间线可交叉印证)
  - `rank` / `categories` / `sum_sub_domains` / `icp`: 流行度/分类/子域规模/备案
- **定位**: 人工研判、钓鱼域名溯源, **全维度检出 (含 Phishing 钓鱼判定, 失陷检测接口不含)**

### 2.3 域名高级查询接口 (扩展项)

- **端点**: `https://api.threatbook.cn/v3/domain/adv_query` — 历史解析 IP、历史 Whois。
- 适合"同源域名发现 / 黑产基础设施拓线"(对应本系统的"提前备货"域名挖掘), 属于二期扩展, 本期不接。

### 2.4 通用约束

- 认证方式: `apikey` 作为**请求参数**传递 (非请求头), 与 URLScan 的 `API-Key` 头不同
- 响应以 `response_code == 0` 判断成功 (非 HTTP 状态码); 超配额/无权限有专门错误码
- 配额按账号套餐计, 免费/个人套餐每日调用次数有限, **批量接口单次 100 个也只计 1 次调用**

## 3. 方案设计: 两级联动 (推荐批量为主 + 单查按需)

### 3.1 总体结构

```
追踪周期结束/手动触发                     分析师点击域名弹窗
        │                                       │
        ▼                                       ▼
 L1 批量打标 (scene/dns)               L2 按需详查 (domain/query)
 143 域名 → 2 次调用                    单域名完整上下文
        │                                       │
        ▼                                       ▼
 threatbook_verdicts 表                内存/DB 缓存 (TTL 24h)
        │                                       │
        ▼                                       ▼
 列表页/卡片风险徽章                    弹窗展示 whois/样本/解析IP/团伙标签
 (恶意·高可信 → 红色 chip)             + permalink 跳转 X 情报中心
```

### 3.2 L1 批量打标层 (scene/dns)

- **触发时机**: 每轮追踪周期 (`run_full_cycle`) 结束后, 或每日定时一次 (可复用 `scheduler` 的 cadence 机制, 建议 `threatbook_seconds = 86400`)
- **查询对象**: frontends 全部域名 + seed C2 域名 + 下载宿主 (从 links 表 download 节点提取 host 部分)
- **分批策略**: 每批 ≤100 个, 当前 148 个对象 → 2 次调用/天
- **落库**: 新表 `threatbook_verdicts (domain, is_malicious, confidence_level, severity, judgments_json, tags_json, permalink, queried_at)`，`INSERT OR REPLACE` 保留最新判定
- **原始证据**: 按现有规范 `dump_evidence("threatbook", ...)` 落盘 `data/evidence/threatbook/`
- **前端呈现**: 仿冒站点卡片/列表增加风险徽章列; "银狐"等团伙标签直接显示为 chip

### 3.3 L2 按需详查层 (domain/query)

- **触发时机**: 仅当分析师点击域名弹窗 (复用现有截图弹窗交互, 增加"微步情报" Tab/区块)
- **缓存**: 参照 `_PROBE_CACHE` 模式做 TTL 缓存 (建议 24h, 情报时效性以天计), 避免重复扣配额
- **字段裁剪**: 用 `exclude=sum_sub_domains,sum_cur_ips` 等裁掉不展示的字段, 减小响应体
- **展示重点**: judgments + tags_classes (是否判"Phishing/银狐") / cur_whois (与 RDAP 交叉印证) / samples (与载荷骨架 sha256 比对) / cur_ips (与 page_ip 比对) / permalink

### 3.4 配置接入 (复用现有机制)

- `config.py`: 新增 `threatbook: CollectorMode`, `API_KEY_COLLECTORS` 加入 `"threatbook"`, `MODE_COLLECTORS` 加入 `"threatbook"`
- 个人中心自动出现模式切换与密钥输入框 (profile.js 的 `KEY_PROVIDERS` 增加微步申请入口 `https://x.threatbook.com/api`)
- mock 模式: 按 dataset 域名生成合理判定 (银狐团伙标签), 保证无密钥也能演示完整链路
- 失败处理: 走 `record_error` 错误账本, 不阻断追踪主流程

## 4. 批量模式 vs 单个详细模式对比

| 维度 | 批量 (scene/dns) | 单查 (domain/query) |
| --- | --- | --- |
| 单次调用容量 | ≤100 个域名/IP | 1 个域名 |
| 配额消耗 (143 域名) | 2 次/轮 | 143 次/轮 (不可接受) |
| 判定信息 | 恶意/可信度/严重级别/威胁类型/团伙标签 | 同左 + 全维度检出 (含 Phishing) |
| 上下文信息 | 无 (仅 permalink) | whois/样本/解析IP/证书/备案/情报来源 |
| 威胁覆盖 | 仅出站场景 (C2/Malware/矿池) | 全维度 (含钓鱼、仿冒) |
| 适用场景 | 全量域名例行打标、告警降噪 | 单域名人工研判、溯源取证 |
| 时延 | 一次网络往返批量返回 | 每域名一次往返 |

**结论: 二者不是二选一, 而是分层组合。**

- 只用批量: 缺少钓鱼判定 (失陷检测接口不检出 Phishing, 而仿冒站点恰恰以钓鱼为主) 和研判上下文, 情报价值打折;
- 只用单查: 143 域名/轮的配额消耗对免费/低配套餐不可持续, 且绝大多数查询结果无人查看, 属于浪费;
- **推荐**: 批量接口做全量"雷达扫描"(低成本发现哪些域名已被微步判黑、有团伙标签), 单查接口做"精确制导"(分析师对可疑目标按需下钻), 配额消耗从 O(n) 降到 O(批次) + O(人工点击), 与本系统"值班流程 + 人工研判"的方法论一致。

### 已知局限

- 失陷检测接口对纯钓鱼域名可能返回非恶意 (覆盖偏出站威胁), L1 徽章需标注"微步出站检测"避免误读为"安全";
- 微步免费配额有限, 若套餐不足可将 L1 频率降为每日一次或仅对"当天注册/高优事件"关联域名打标;
- `apikey` 走 URL 参数, 注意日志脱敏 (系统日志与 evidence 落盘时应掩码 apikey)。

## 5. 实施步骤建议 (预估工作量)

1. `collectors/threatbook.py`: Provider 子类, `verdict_batch()` + `domain_detail()` 双方法, mock/live 双路径 (~0.5 天)
2. `db.py`: `threatbook_verdicts` 表 + 迁移 (~0.5 小时)
3. `tracker.py` / `scheduler.py`: L1 批量打标周期接入 (~0.5 天)
4. 路由 `routers/threatbook.py`: `GET /threatbook/{domain}` (L2 详查, 带缓存) (~0.5 天)
5. 前端: 列表徽章 + 弹窗情报区块 + 个人中心配置项 (~1 天)
6. 测试: mock 判定单测 + API 集成测试 (~0.5 天)
