"""FastAPI 应用装配 (展示层入口)。

职责:
    - 挂载 /api 路由;
    - 托管静态 Web 仪表盘 (web/);
    - 启动时初始化数据库, 若为空则自动执行种子回放;
    - 按配置启动分级调度器。

运行:
    uv run uvicorn liehu.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import current_user_id, ensure_default_admin
from .config import reload_overrides_from_db, settings
from .db import get_connection, init_db
from .routers import api_router
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("liehu")


def _db_is_empty() -> bool:
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM frontends").fetchone()
        return row["c"] == 0
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期: 初始化 + 自动种子 + 鉴权初始化 + 调度器。"""
    init_db()
    ensure_default_admin()            # 首次启动种子默认管理员 admin/admin
    reload_overrides_from_db()        # 回填个人中心保存的 API 密钥/模式
    if _db_is_empty():
        logger.info("数据库为空, 执行种子回放 ...")
        from .seed import seed
        seed()
    if settings.scheduler_enabled:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="SilverFoxHunter 银狐猎手",
    description="基于'壳/线/包'三层方法论的银狐仿冒下载链威胁情报追踪系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok", "system": "silverfoxhunter"}


# 托管静态仪表盘
if settings.web_dir.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(settings.web_dir / "assets"))
        if (settings.web_dir / "assets").exists()
        else StaticFiles(directory=str(settings.web_dir)),
        name="assets",
    )

    def _logged_in(sfh_session: str | None) -> bool:
        return current_user_id(sfh_session) is not None

    @app.get("/login")
    def login_page() -> FileResponse:
        """登录页。"""
        return FileResponse(str(settings.web_dir / "login.html"))

    @app.get("/")
    def index(sfh_session: str | None = Cookie(default=None)):
        """仪表盘首页 (需登录, 否则跳登录页)。"""
        if not _logged_in(sfh_session):
            return RedirectResponse(url="/login", status_code=302)
        return FileResponse(str(settings.web_dir / "index.html"))

    @app.get("/profile")
    def profile_page(sfh_session: str | None = Cookie(default=None)):
        """个人中心 (需登录, 否则跳登录页)。"""
        if not _logged_in(sfh_session):
            return RedirectResponse(url="/login", status_code=302)
        return FileResponse(str(settings.web_dir / "profile.html"))
