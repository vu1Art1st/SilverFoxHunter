"""调度层 (对应文章第五节"值班流程")。

自动化只负责按不同速度重复手工追清的一条链:
    - 前台: 每 5-10 分钟查询最近 15 分钟的重叠窗口;
    - 活动控制端与供包路径: 每 3-5 分钟留一轮样本;
    - CT / 注册数据 / DNS: 按域名生命周期刷新。

使用 APScheduler 的后台调度器管理分级任务。
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import tracker
from .collectors import build_collectors
from .config import settings

logger = logging.getLogger("liehu.scheduler")

_scheduler: BackgroundScheduler | None = None


def _safe(fn, name: str):
    """包一层异常保护, 避免单次任务异常导致调度线程退出。"""
    def wrapper():
        try:
            collectors = build_collectors()
            with tracker.db_session() as conn:
                result = fn(collectors, conn)
            logger.info("cycle %s done: %s", name, result)
        except Exception:  # noqa: BLE001
            logger.exception("cycle %s failed", name)
    return wrapper


def start_scheduler() -> BackgroundScheduler:
    """启动分级调度器 (幂等)。"""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    tracker.init_db()
    cad = settings.cadence
    sched = BackgroundScheduler(timezone="UTC")

    sched.add_job(_safe(tracker.run_frontend_cycle, "frontend"),
                  "interval", seconds=cad.frontend_seconds, id="frontend",
                  next_run_time=None)
    sched.add_job(_safe(tracker.run_control_cycle, "control"),
                  "interval", seconds=cad.control_seconds, id="control")
    sched.add_job(_safe(tracker.run_payload_cycle, "payload"),
                  "interval", seconds=cad.payload_seconds, id="payload")
    sched.add_job(_safe(tracker.run_dns_cycle, "dns"),
                  "interval", seconds=cad.dns_seconds, id="dns")

    sched.start()
    _scheduler = sched
    logger.info(
        "scheduler started: frontend=%ss control=%ss payload=%ss dns=%ss",
        cad.frontend_seconds, cad.control_seconds,
        cad.payload_seconds, cad.dns_seconds,
    )
    return sched


def stop_scheduler() -> None:
    """停止调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
