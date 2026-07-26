"""采集器基础设施。

定义 Provider 抽象 (Mock / Live)、原始证据落盘、错误账本记录等工具。
对应文章"这套管道并不重": 公开观察面 (URLScan/CertSpotter/RDAP/DoH) 提供数据,
原始响应按时间落盘, 采集失败单独记账 (errors 表)。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings


def now_iso() -> str:
    """当前时间的 ISO8601 字符串 (UTC)。"""
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    """计算 bytes 的 SHA-256 十六进制。"""
    return hashlib.sha256(data).hexdigest()


def dump_evidence(source: str, name: str, payload: object) -> Path:
    """将原始响应按时间落盘到 evidence 目录, 返回文件路径。

    对应文章"每轮原始 JSON 先落盘"。
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    safe_name = name.replace("/", "_").replace(":", "_")
    out_dir = settings.evidence_dir / source
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ts}_{safe_name}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
    return path


def record_error(conn, source: str, target: str | None, reason: str) -> None:
    """向 errors 表写入一条采集错误 (errors.jsonl 的 DB 版本)。"""
    conn.execute(
        "INSERT INTO errors (source, target, reason, observed_at) "
        "VALUES (?, ?, ?, ?)",
        (source, target, reason, now_iso()),
    )


class Provider:
    """采集器 Provider 基类。

    子类需实现 Mock / Live 两种数据获取逻辑。混合模式下由 config 决定走哪条路径。
    """

    #: 数据源名称, 用于错误账本与证据落盘目录
    source: str = "base"

    def __init__(self, mode: str = "mock", api_key: str | None = None) -> None:
        self.mode = mode
        self.api_key = api_key

    @property
    def is_live(self) -> bool:
        return self.mode.lower() == "live"
