"""数据库层 (SQLite)。

使用 Python 内置 sqlite3, 保持轻量。提供连接管理、初始化建表以及行->dict
的转换工具。对应文章"状态存储层": 不同数据源各记各的水位, 原始证据落盘,
SQLite / JSON 保存状态。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .config import settings

# ---- 建表 DDL ----------------------------------------------------------------

SCHEMA = """
-- 壳: 前台页面状态卡
CREATE TABLE IF NOT EXISTS frontends (
    domain           TEXT PRIMARY KEY,     -- 归一化后的 page.domain
    first_seen       TEXT,                 -- 首次公开记录时间 (ISO)
    last_seen        TEXT,                 -- 最近一次记录时间
    title            TEXT,                 -- 当前页面标题
    page_ip          TEXT,                 -- 主页面 IP
    http_status      INTEGER,              -- HTTP 状态
    control_domain   TEXT,                 -- 请求的控制接口域名 (线连接件)
    control_api      TEXT,                 -- 完整控制接口 URL (如 fezhx.com/api.php)
    analytics_id     TEXT,                 -- 51.LA 等分析 ID
    theme            TEXT,                 -- 题材: office/vpn/logistics/music...
    registered_at    TEXT,                 -- 注册时间 (RDAP/WHOIS)
    ns               TEXT,                 -- NS 记录 (逗号分隔)
    day_class        TEXT,                 -- 当天分类: same_day/preexisting/rescan/content_change
    campaign         TEXT,                 -- 归因战役: noah/fezhx/unknown
    evidence_url     TEXT,                 -- 原始证据链接
    task_uuid        TEXT,                 -- URLScan task.uuid (去重键)
    updated_at       TEXT
);

-- 线: 控制接口分时采样
CREATE TABLE IF NOT EXISTS control_samples (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    control_domain   TEXT NOT NULL,
    control_api      TEXT NOT NULL,
    observed_at      TEXT NOT NULL,         -- 观察时间
    http_status      INTEGER,
    resp_sha256      TEXT,                  -- 响应体 SHA-256
    resp_length      INTEGER,               -- 响应长度
    download_link    TEXT,                  -- 解析出的 download_link
    headers_json     TEXT,                  -- 响应头快照
    error            TEXT                   -- 错误信息 (若采集失败)
);

-- 包: 载荷样本结构指标
CREATE TABLE IF NOT EXISTS payloads (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    download_url     TEXT NOT NULL,         -- 下载地址 (如 gnrrn2821.com/22setup)
    observed_at      TEXT NOT NULL,
    full_sha256      TEXT,                  -- 完整文件 SHA-256 (秒级轮换)
    msi_size         INTEGER,               -- MSI 大小
    embedded_pe_size INTEGER,               -- 内嵌 PE 大小
    pe_entry_rva     INTEGER,               -- PE 入口 RVA
    stable_sha256    TEXT,                  -- 去尾字节后的稳定区 SHA-256
    embedded_pe_sha256 TEXT,                -- 内嵌 PE SHA-256
    imphash          TEXT,                  -- 导入哈希
    ole_stream_count INTEGER,               -- OLE 流数量
    ole_identical    INTEGER,               -- 与上一轮逐字节一致的流数
    wix_version      TEXT,                  -- 安装器元数据
    structure_id     TEXT                   -- 生产骨架标识 (结构指纹)
);

-- DNS 快照
CREATE TABLE IF NOT EXISTS dns_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    domain           TEXT NOT NULL,
    observed_at      TEXT NOT NULL,
    dns_status       INTEGER,               -- Google DoH Status (0=NOERROR,3=NXDOMAIN)
    a_records        TEXT,                  -- A 记录 JSON
    aaaa_records     TEXT,
    cname_records    TEXT,
    ns_records       TEXT
);

-- 差异事件 (只推变化)
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type       TEXT NOT NULL,         -- NEW_FRONTEND / CONTROL_CHANGE / ...
    object_ref       TEXT NOT NULL,         -- 关联对象 (域名/接口/下载路径)
    priority         TEXT NOT NULL,         -- high / pending / watch
    first_observed   TEXT,                  -- 首次观察时间
    last_observed    TEXT,                  -- 最近观察时间
    prev_state       TEXT,                  -- 上一状态
    curr_state       TEXT,                  -- 当前状态
    fact             TEXT,                  -- 触发它的事实
    evidence_url     TEXT,                  -- 证据链接
    created_at       TEXT NOT NULL
);

-- 采集错误账本 (errors.jsonl 的 DB 版本, 与 IOC 表一样重要)
CREATE TABLE IF NOT EXISTS errors (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL,         -- urlscan/rdap/dns/control/payload
    target           TEXT,                  -- 相关目标
    reason           TEXT NOT NULL,         -- quota/invisible/whois_timeout/servfail...
    observed_at      TEXT NOT NULL
);

-- 战役连接件 (壳/线/包 关系图边)
CREATE TABLE IF NOT EXISTS links (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    src              TEXT NOT NULL,         -- 源节点 id
    src_type         TEXT NOT NULL,         -- frontend/control/analytics/download/payload
    dst              TEXT NOT NULL,         -- 目标节点 id
    dst_type         TEXT NOT NULL,
    relation         TEXT NOT NULL,         -- requests/binds/returns/rotates
    campaign         TEXT,
    UNIQUE(src, dst, relation)
);

-- 键值元数据 (记录 mock 回放轮次等运行状态)
CREATE TABLE IF NOT EXISTS meta (
    key              TEXT PRIMARY KEY,
    value            TEXT
);

-- 用户 (单机自用: 单一内置管理员, 可改用户名/密码/头像)
CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT NOT NULL UNIQUE,
    pw_salt          TEXT NOT NULL,         -- 密码盐 (hex)
    pw_hash          TEXT NOT NULL,         -- pbkdf2_hmac(sha256) 摘要 (hex)
    avatar           TEXT,                  -- 头像 base64 dataURL (可空)
    created_at       TEXT,
    updated_at       TEXT
);

-- 应用运行配置 (会话密钥、API 密钥、采集器模式覆盖等)
CREATE TABLE IF NOT EXISTS app_settings (
    key              TEXT PRIMARY KEY,
    value            TEXT
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """创建一个新的 SQLite 连接 (row_factory 返回 dict 风格)。"""
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """初始化数据库 (幂等建表)。"""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """上下文管理的数据库会话, 自动提交 / 回滚 / 关闭。"""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """将 sqlite3.Row 转为普通 dict。"""
    return dict(row) if row is not None else None


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    """将 Row 列表转为 dict 列表。"""
    return [dict(r) for r in rows]
