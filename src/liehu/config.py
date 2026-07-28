"""系统配置。

集中管理运行模式 (mock / live)、外部数据源 API Key、分级采集节奏以及
数据存储路径。混合模式下默认使用 mock 数据源, 配置对应 API Key 后可将
单个采集器切换到 live。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录 (src/liehu/config.py -> 上溯到项目根)
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"  # 原始响应落盘目录
WEB_DIR = Path(__file__).resolve().parent / "web"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class CollectorMode:
    """单个采集器的运行模式配置。

    mode 取值 "mock" 或 "live"。live 模式需要提供 api_key (若数据源要求)。
    """

    mode: str = "mock"
    api_key: str | None = None

    @property
    def is_live(self) -> bool:
        return self.mode.lower() == "live"


@dataclass
class Cadence:
    """分级采集节奏 (秒)。对应文章"值班流程"中不同数据源的刷新频率。"""

    frontend_seconds: int = 300      # 前台: 5-10 分钟查最近 15 分钟重叠窗
    frontend_window_minutes: int = 15
    control_seconds: int = 180       # 活动控制端: 3-5 分钟一轮采样
    dns_seconds: int = 600           # DNS: 按生命周期
    ct_seconds: int = 1800           # CT / 注册数据: 较慢
    payload_seconds: int = 300       # 供包路径静态解析
    threatbook_seconds: int = 86400  # 微步 L1 批量打标: 每日一次 (配额友好)


@dataclass
class Settings:
    """全局设置。"""

    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("LIEHU_DB_PATH", str(DATA_DIR / "liehu.db")))
    )
    evidence_dir: Path = EVIDENCE_DIR
    web_dir: Path = WEB_DIR

    # 各采集器运行模式 (混合模式: 可分别切换)
    urlscan: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_URLSCAN_MODE", "mock"),
        api_key=os.getenv("URLSCAN_API_KEY"),
    ))
    certspotter: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_CERTSPOTTER_MODE", "mock"),
        api_key=os.getenv("CERTSPOTTER_API_KEY"),
    ))
    rdap: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_RDAP_MODE", "mock"),
    ))
    doh: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_DOH_MODE", "mock"),
    ))
    control: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_CONTROL_MODE", "mock"),
    ))
    payload: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_PAYLOAD_MODE", "mock"),
    ))
    # 微步在线情报: api_key 支持多个 KEY (逗号/分号/换行分隔), 限额时自动切换
    threatbook: CollectorMode = field(default_factory=lambda: CollectorMode(
        mode=os.getenv("LIEHU_THREATBOOK_MODE", "mock"),
        api_key=os.getenv("THREATBOOK_API_KEYS"),
    ))

    cadence: Cadence = field(default_factory=Cadence)

    # 是否在应用启动时自动运行调度器
    scheduler_enabled: bool = field(
        default_factory=lambda: _env_bool("LIEHU_SCHEDULER", True)
    )

    # 已知的活动控制接口 (文章 7·23 晚间水位), 作为追踪起点连接件
    seed_control_domains: tuple[str, ...] = (
        "noah-admin.site",
        "fezhx.com",
    )


settings = Settings()
"""全局单例配置对象。"""


# 可配置 API 密钥的采集器 (certspotter 已切换为免费 crt.sh, 无需密钥;
# threatbook 支持录入多个 KEY, 用逗号/分号/换行分隔, 达到限额自动切换下一个)
API_KEY_COLLECTORS = ("urlscan", "threatbook")
# 可切换 mock/live 模式的采集器
MODE_COLLECTORS = ("urlscan", "certspotter", "rdap", "doh", "control", "payload", "threatbook")


def parse_api_keys(raw: str | None) -> list[str]:
    """将多 KEY 配置串解析为密钥列表 (逗号/分号/换行分隔, 去空白去重保序)。"""
    if not raw:
        return []
    normalized = raw.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
    seen: list[str] = []
    for part in normalized.split("\n"):
        key = part.strip()
        if key and key not in seen:
            seen.append(key)
    return seen


def reload_overrides_from_db() -> None:
    """从 app_settings 读取运行时覆盖, 回填到 settings 单例。

    覆盖项: 各采集器 mode (mode.<name>) 与 API 密钥 (apikey.<name>)。
    使个人中心保存的配置对调度器/采集器即时生效。
    延迟导入 db 以避免循环依赖。
    """
    from .db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    except Exception:
        return
    finally:
        conn.close()

    kv = {r["key"]: r["value"] for r in rows}
    for name in MODE_COLLECTORS:
        collector: CollectorMode = getattr(settings, name)
        mode = kv.get(f"mode.{name}")
        if mode in {"mock", "live"}:
            collector.mode = mode
        if name in API_KEY_COLLECTORS:
            key = kv.get(f"apikey.{name}")
            if key is not None:
                collector.api_key = key or None


def save_overrides_to_db(modes: dict[str, str], api_keys: dict[str, str]) -> None:
    """将个人中心提交的模式与 API 密钥写入 app_settings, 并立即 reload。"""
    from .db import get_connection

    conn = get_connection()
    try:
        for name, mode in modes.items():
            if name in MODE_COLLECTORS and mode in {"mock", "live"}:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
                    (f"mode.{name}", mode),
                )
        for name, key in api_keys.items():
            if name in API_KEY_COLLECTORS:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
                    (f"apikey.{name}", key or ""),
                )
                if name == "threatbook":
                    # 密钥集合变更后从第一个 KEY 重新开始轮换
                    conn.execute(
                        "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
                        ("threatbook.key_index", "0"),
                    )
        conn.commit()
    finally:
        conn.close()
    reload_overrides_from_db()
