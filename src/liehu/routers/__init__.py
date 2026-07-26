"""API 路由包。

按资源拆分路由: stats(水位统计)、frontends(壳)、controls(线)、payloads(包)、
events(差异事件/差异卡)、campaigns(战役关联图)。所有读接口直接查询 SQLite。

鉴权: 业务数据路由统一挂载 require_user 依赖 (未登录 401); auth 路由 (登录/登出)
不设防, account 路由 (个人中心) 各接口自身声明依赖。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_user
from .account import router as account_router
from .auth import router as auth_router
from .campaigns import router as campaigns_router
from .controls import router as controls_router
from .events import router as events_router
from .frontends import router as frontends_router
from .payloads import router as payloads_router
from .stats import router as stats_router

api_router = APIRouter(prefix="/api")

# 不设防: 登录 / 登出 / 当前用户
api_router.include_router(auth_router)

# 个人中心: 依赖在各路由内部声明
api_router.include_router(account_router)

# 业务数据路由: 统一要求已登录
_protected = [Depends(require_user)]
api_router.include_router(stats_router, dependencies=_protected)
api_router.include_router(frontends_router, dependencies=_protected)
api_router.include_router(controls_router, dependencies=_protected)
api_router.include_router(payloads_router, dependencies=_protected)
api_router.include_router(events_router, dependencies=_protected)
api_router.include_router(campaigns_router, dependencies=_protected)

__all__ = ["api_router"]
