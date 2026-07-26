# 快速开始

← 返回 [Wiki 首页](Home.md)

## 前置条件

- **Python ≥ 3.10**
- **[uv](https://docs.astral.sh/uv/)** —— 本项目统一用 uv 管理虚拟环境与依赖（`uv.lock` 锁定版本）。
- 默认 **mock 模式** 零外部依赖，无需任何 API Key 即可完整演示三层追踪。

## 安装与运行

```bash
# 1. 安装依赖（uv 自动创建 .venv 并按 uv.lock 还原）
uv sync

# 2. 启动服务（首次为空库会自动种子回放, 复原 7·23 水位）
uv run uvicorn liehu.main:app --host 127.0.0.1 --port 8010
```

启动后访问：

- **仪表盘**：<http://127.0.0.1:8010>
- **OpenAPI 交互文档**：<http://127.0.0.1:8010/docs>
- **健康检查**：<http://127.0.0.1:8010/health>

> **Windows PowerShell 提示**：设置环境变量用 `$env:NAME="value"`（不是 bash 的 `NAME=value`），
> 且 `&` 会被解释为后台 Job。例如关闭调度器启动：
> `$env:LIEHU_SCHEDULER="0"; uv run uvicorn liehu.main:app --port 8010`

## 种子数据（7·23 水位复原）

系统内置一份**忠实复原原文 7·23 晚间观测水位**的 mock 数据集。首次启动若数据库为空，
会在 `lifespan` 中自动种子回放。也可手动执行：

```bash
# 重新生成/重放种子数据
uv run python -m liehu.seed

# 分析逻辑变更后, 清空所有表并重放（让持久化的事件/分类反映最新算法）
uv run python scripts/reset_seed.py
```

> **为什么需要 `reset_seed.py`？** 种子回放是"追加"式的；当你改动了分析算法
> （如稳定区哈希 / 差异判定），需要清空旧的持久化事件后重放，才能让仪表盘反映最新分类。
> 该脚本在进程内 `DELETE FROM` 所有表后重放，规避了 Windows 下运行中进程锁住 SQLite 文件的问题。

## 运行测试

```bash
uv run pytest -q      # 预期 34 passed
```

## 数据与存储

- SQLite 数据库：`data/liehu.db`（WAL 模式）。
- 采集原始响应证据落盘：`data/evidence/`。
- 这两个目录在首次运行时自动创建。

## 常见问题

**Q：端口被占用 `error while attempting to bind on address ... 8010`？**
说明已有实例在运行该端口，换一个端口（`--port 8011`）或先停止旧进程。

**Q：只想看静态回放、不要后台不断产生新事件？**
设置 `LIEHU_SCHEDULER=0` 关闭分级调度器。

**Q：如何接入真实数据源？**
见 [配置指南](Configuration.md)，将对应采集器 `LIEHU_<NAME>_MODE` 切到 `live` 并提供 API Key。

---

下一步：[核心方法论](Methodology.md) · [Web 仪表盘](Dashboard.md)
