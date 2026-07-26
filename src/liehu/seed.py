"""数据库初始化与种子回放。

运行本脚本将:
    1. 初始化 SQLite 表结构;
    2. 执行一次前台发现周期, 落地文章 7·23 的 143 个前台;
    3. 依次回放控制端各轮采样, 触发 ROUTE_MERGE;
    4. 依次回放载荷各轮解析, 触发 PAYLOAD_STRUCTURAL_CHANGE / PAYLOAD_ROTATION;
    5. 采集 DNS 快照 (page-admin.site 为 NXDOMAIN)。

用法:
    uv run python -m liehu.seed
"""

from __future__ import annotations

from . import tracker
from .collectors import build_collectors
from .db import db_session, init_db
from .mock import dataset


def seed() -> dict:
    """执行完整种子回放, 返回统计结果。"""
    init_db()
    collectors = build_collectors()
    summary: dict = {"frontend": None, "control_rounds": [], "payload_rounds": [], "dns": []}

    with db_session() as conn:
        # 1) 前台发现 (143 个)
        summary["frontend"] = tracker.run_frontend_cycle(collectors, conn)

        # 2) 控制端: 回放全部轮次 (7·22 分离 -> 7·23 合流)
        for _ in range(len(dataset.CONTROL_ROUNDS)):
            summary["control_rounds"].append(
                tracker.run_control_cycle(collectors, conn)
            )

        # 3) 载荷: 回放全部轮次 (9.1MB -> 6.9MB 结构换代 -> 哈希轮换)
        for _ in range(len(dataset.PAYLOAD_ROUNDS)):
            summary["payload_rounds"].append(
                tracker.run_payload_cycle(collectors, conn)
            )

        # 4) DNS 快照
        summary["dns"].append(tracker.run_dns_cycle(collectors, conn))

    return summary


def main() -> None:
    result = seed()
    fe = result["frontend"]
    ev_total = (
        fe["events"]
        + sum(r["events"] for r in result["control_rounds"])
        + sum(r["events"] for r in result["payload_rounds"])
        + sum(r["events"] for r in result["dns"])
    )
    print("=" * 56)
    print("SilverFoxHunter 银狐猎手 · 种子回放完成")
    print("=" * 56)
    print(f"前台 (壳)      : {fe['frontends']} 个")
    print(f"控制端轮次 (线): {len(result['control_rounds'])} 轮")
    print(f"载荷轮次 (包)  : {len(result['payload_rounds'])} 轮")
    print(f"差异事件总数   : {ev_total} 条")
    print("=" * 56)


if __name__ == "__main__":
    main()
