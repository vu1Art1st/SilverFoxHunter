"""水位统计路由 (总览页数据)。

对应文章的水位口径: 记录数 vs 站点数、noah/fezhx 分布、当天分类
(同日/首见/复扫/内容变化), 以及各数据源的运行模式与错误账本。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..db import get_connection
from ..mock import dataset

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats() -> dict:
    """返回总览水位统计。"""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM frontends").fetchone()["c"]

        by_campaign = {
            row["campaign"]: row["c"]
            for row in conn.execute(
                "SELECT campaign, COUNT(*) AS c FROM frontends GROUP BY campaign"
            ).fetchall()
        }
        by_dayclass = {
            row["day_class"]: row["c"]
            for row in conn.execute(
                "SELECT day_class, COUNT(*) AS c FROM frontends GROUP BY day_class"
            ).fetchall()
        }
        by_theme = {
            row["theme"]: row["c"]
            for row in conn.execute(
                "SELECT theme, COUNT(*) AS c FROM frontends GROUP BY theme"
            ).fetchall()
        }
        events_by_priority = {
            row["priority"]: row["c"]
            for row in conn.execute(
                "SELECT priority, COUNT(*) AS c FROM events GROUP BY priority"
            ).fetchall()
        }
        event_total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        error_total = conn.execute("SELECT COUNT(*) AS c FROM errors").fetchone()["c"]
    finally:
        conn.close()

    return {
        "water_mark": "2026-07-23T19:36:43+08:00",
        "frontend_total": total,
        "by_campaign": by_campaign,
        "by_dayclass": by_dayclass,
        "by_theme": by_theme,
        "event_total": event_total,
        "events_by_priority": events_by_priority,
        "error_total": error_total,
        "modes": {
            "urlscan": settings.urlscan.mode,
            "certspotter": settings.certspotter.mode,
            "rdap": settings.rdap.mode,
            "doh": settings.doh.mode,
            "control": settings.control.mode,
            "payload": settings.payload.mode,
        },
        "starting_iocs": dataset.starting_iocs(),
    }
