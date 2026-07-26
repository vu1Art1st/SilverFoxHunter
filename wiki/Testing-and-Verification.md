# 测试与验证

← 返回 [Wiki 首页](Home.md)

`pytest` 覆盖分析层纯函数与 API 集成，确保三层追踪逻辑与文章 7·23 水位一致。

```bash
uv run pytest -q     # 34 passed
```

## 测试覆盖

| 测试文件 | 覆盖 |
|----------|------|
| [`test_stablehash.py`](../tests/test_stablehash.py) | 稳定区哈希、纯轮换 vs 结构换代判定（含尾字节 006f/007f/008f 案例） |
| [`test_correlation.py`](../tests/test_correlation.py) | 多时钟分类、战役归因、连接件置信度、秒级注册批次、ROUTE_MERGE |
| [`test_dedup.py`](../tests/test_dedup.py) | 域名归一化、uuid 去重、记录数 vs 站点数 |
| [`test_diff.py`](../tests/test_diff.py) | 前台/控制/载荷/DNS 差异事件（结构换代优先级） |
| [`test_api_integration.py`](../tests/test_api_integration.py) | TestClient 验证 143 前台、noah=111/fezhx=32、关联图三层、优先级过滤、载荷骨架 |

集成测试导入前设置 `os.environ["LIEHU_SCHEDULER"] = "0"`，用 FastAPI `TestClient` 触发
`lifespan` 自动 seed，避免后台调度器干扰断言。

## 种子回放验证

```bash
uv run python -m liehu.seed          # 首次回放
uv run python scripts/reset_seed.py  # 分析逻辑变更后重置并重放
```

复原文章 7·23 晚间观测水位：

- **前台 143**：noah 战役 111 + fezhx 战役 32
- **差异事件 291**：`NEW_FRONTEND` 143 + `FIRST_PUBLIC` 143 + `ROUTE_MERGE` 1 +
  `CONTROL_CHANGE` 1 + `PAYLOAD_STRUCTURAL_CHANGE` 1 + `PAYLOAD_ROTATION` 2
- **关系图边 290**
- **载荷换代**：MSI 9,158,656 B → 6,975,488 B（结构换代 1 次）+ 尾字节轮换 2 次
- **稳定指纹**：imphash `9b760feffec4fca9c313889f9a05ee36`、WiX 4.0.5.0、OLE 25 流 22 相同

## 关键缺陷修正（回归案例）

早期 `stablehash.is_structural_change` 误用 `prev.ole_identical != prev.ole_stream_count`
（同一样本内 identical/total 比值，是数据属性而非变化信号），导致 22/25 的样本被恒判为结构换代。

已修正为比较**两次观测之间**的 `ole_stream_count`，使 7·23 载荷正确输出
**1 次结构换代 + 2 次尾字节轮换**。该缺陷正是由单元测试
`test_pure_rotation_true_when_only_full_hash_changes` 暴露，是"测试驱动定位真实 bug"的实例。

> `scripts/reset_seed.py` 在进程内清空所有表后重放种子，用于分析逻辑变更后让持久化的
> 事件/分类反映最新算法（规避运行中进程锁住 SQLite 文件的问题）。

## 交付物浏览器验证

用系统 Chrome headless 对运行中的 <http://127.0.0.1:8010> 采集了 6 个标签页截图
（`docs/dashboard_*.png`），确认 ECharts 图表、力导向关联图、差异卡、结构对比表全部完整渲染，
控制台零报错，`/api` 请求全部成功。

---

延伸阅读：[核心方法论](Methodology.md) · [Web 仪表盘](Dashboard.md) · [数据模型](Data-Model.md)
