"""pytest 共享夹具与测试隔离。

在导入任何 liehu 模块之前设置环境变量:
    - 关闭后台调度器, 避免干扰;
    - 将数据库指向 .pytest_cache 下的独立文件, 使测试不污染 data/liehu.db。
"""

from __future__ import annotations

import os
from pathlib import Path

_TEST_DB = Path(__file__).resolve().parents[1] / ".pytest_cache" / "liehu_test.db"
_TEST_DB.parent.mkdir(parents=True, exist_ok=True)
# 每次会话使用全新数据库, 保证种子回放与默认管理员可复现
for suffix in ("", "-wal", "-shm"):
    p = Path(str(_TEST_DB) + suffix)
    if p.exists():
        p.unlink()

os.environ["LIEHU_SCHEDULER"] = "0"
os.environ["LIEHU_DB_PATH"] = str(_TEST_DB)
os.environ.setdefault("LIEHU_SECRET", "test-secret-key")

import pytest
from fastapi.testclient import TestClient

from liehu.auth import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from liehu.main import app


@pytest.fixture(scope="session")
def anon_client():
    """未认证的 TestClient (触发 lifespan: 初始化 + 种子 + 默认管理员)。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client(anon_client):
    """已登录 (admin/admin) 的 TestClient; 每个测试后登出以复位会话。"""
    r = anon_client.post(
        "/api/auth/login",
        json={"username": DEFAULT_ADMIN_USERNAME, "password": DEFAULT_ADMIN_PASSWORD},
    )
    assert r.status_code == 200, f"默认管理员登录失败: {r.status_code} {r.text}"
    yield anon_client
    anon_client.post("/api/auth/logout")
