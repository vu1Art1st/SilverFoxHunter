# 核心方法论

← 返回 [Wiki 首页](Home.md)

本页解释猎狐系统背后的追踪思路，对应原文《我是怎么追踪银狐新域名的》各节。核心理念是：
**不要盯着变化最快的那一层，而是沿着"壳 → 线 → 包"从易变到持久逐层下沉，抓住相对稳定的
"连接件"来关联与追踪。**

## 1. 三层模型（壳 / 线 / 包）

| 层 | 别名 | 内容 | 易变程度 | 追踪价值 |
|----|------|------|----------|----------|
| **壳** | Shell / 前台 | 仿冒页面域名、标题、品牌题材 | 最快（当天轮换） | 低（单域名寿命短） |
| **线** | Line / 控制线 | 控制接口 `api.php`、`download_link`、分析 ID、下载路径 | 中（数天~数周） | 高（跨壳复用） |
| **包** | Package / 载荷 | MSI / 内嵌 PE；完整哈希秒级轮换，结构骨架持久 | 完整哈希最快 / 骨架最慢 | 高（稳定区哈希锁定生产线） |

题材覆盖：物流查询 / Apple Music / 办公软件 / 券商 / VPN / AI 工具等。

## 2. 多时钟关联

用 4 只"钟"交叉判断域名的真实"年龄"与用途，单看一只钟会误判：

- **CT 证书透明日志**（CertSpotter）—— 证书首见时间
- **RDAP / WHOIS** —— 注册时间、注册商
- **DNS（DoH）** —— A / NS 记录与解析状态（活跃 / NXDOMAIN）
- **URLScan** —— 首次公开扫描记录

> **典型误判修正**：某域名"首见"早于"注册时间"，其实是**历史域名被重新注册**（reactivated），
> 而非当天新做。分类器 `classify_registration()` 据此产出 `same_day` / `preexisting` / `reactivated`。

## 3. 连接件归因

只有**多项强连接件同时对上**才确认关联，避免噪声聚类。加权打分（`confidence()`）：

| 连接件 | 权重 | 说明 |
|--------|------|------|
| 精确控制接口 | **5** | 如 `noah-admin.site/api.php` —— 最强连接件 |
| 相同分析 ID | **3** | 如 `3Q3R0HhFsRZ06Tr8` |
| 秒级注册 + 相邻 IP | **2** | 批处理痕迹（如 Apple Music 四站数秒内注册） |
| 共享 IP / ASN / 注册商 / NS / 模板 | **1** | 仅作**候选**，不进关联集合 |

命中控制接口，或"分析 ID + 相邻注册"共现即判 `confirmed`，否则 `candidate`。
`detect_adjacent_registration()` 以滑窗检测秒级注册批次。

## 4. 稳定区哈希

载荷完整哈希（`full_sha256`）秒级轮换（末尾字节 006f / 007f / 008f……），
去掉不稳定末尾字节后的**稳定区 SHA-256** 才能回答"这批文件来自哪套生产骨架"。
配合 imphash、内嵌 PE 哈希、OLE 流结构、入口 RVA 共同构成"结构骨架指纹"。

- `stable_region_sha256(data, trim_tail=2)`：去尾字节后的稳定区哈希。
- `is_pure_rotation(prev, curr)`：完整哈希变，但稳定区 / 内嵌 PE / imphash / 结构 ID 不变 ⇒ **纯轮换**。
- `is_structural_change(prev, curr)`：稳定区、内嵌 PE、结构 ID、入口 RVA 或 **OLE 流数** 在两次观测之间变化 ⇒ **结构换代**。

> **实现要点**：`is_structural_change` 比较的是**两次观测之间**的 `ole_stream_count`，
> 而非同一样本内 identical/total 的比值（后者是数据属性而非变化信号）。据此 7·23 载荷正确输出
> **1 次结构换代 + 2 次尾字节轮换**，与原文一致。

## 5. 告警只推变化

持续监控产生的不是快照，而是**差异事件流**——只有对象状态发生有意义的变化才推送，
并按优先级分级、落到不同处置渠道（`alerting.py`）：

| 优先级 | 含义 | 典型事件 |
|--------|------|----------|
| `high` | 高优处置 | `ROUTE_MERGE` / `CONTROL_CHANGE` / `PAYLOAD_STRUCTURAL_CHANGE` / `NEW_FRONTEND` |
| `pending` | 待确认 | `FIRST_PUBLIC` |
| `watch` | 观察池 | `PAYLOAD_ROTATION`（纯尾字节轮换） |

`build_diff_card()` 把事件渲染为差异卡：对象、首见 / 最近、上一状态、当前状态、事实、落点、证据链接。

## 6. 复原的 7·23 水位

- **143 个前台**：noah 战役 111 个 + fezhx 战役 32 个
- **控制线**：`noah-admin.site/api.php`、`fezhx.com/api.php`（活跃），`page-admin.site/api.php`（NXDOMAIN）
- **路径合流**：7·22 两条控制线各自下载路径 → 7·23 合流到 `www.gnrrn2821.com/22setup`（`ROUTE_MERGE`）
- **载荷换代**：MSI 9,158,656 B → 6,975,488 B（结构换代 1 次）+ 尾字节轮换 2 次
- **稳定指纹**：imphash `9b760feffec4fca9c313889f9a05ee36`、WiX 4.0.5.0、OLE 25 流 22 相同

---

延伸阅读：[系统架构](Architecture.md) · [数据模型](Data-Model.md)
