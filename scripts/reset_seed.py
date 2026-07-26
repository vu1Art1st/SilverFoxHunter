"""重置并重放种子: 清空所有表 (含 meta 轮次指针) 后重新执行种子回放。

用于在分析逻辑变更后, 让持久化的事件/分类反映最新算法。
"""

from liehu import seed
from liehu.db import get_connection, init_db

TABLES = [
    "events", "links", "payloads", "control_samples",
    "dns_snapshots", "errors", "frontends", "meta",
]


def reset() -> None:
    init_db()
    conn = get_connection()
    try:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    reset()
    seed.main()
