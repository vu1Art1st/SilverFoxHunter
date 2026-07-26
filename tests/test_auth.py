"""鉴权与个人中心集成测试。

覆盖: 登录成功/失败、未授权 401、改密码后旧密码失效 (并复位)、
API 密钥保存后掩码返回。数据库隔离见 conftest.py。
"""

from __future__ import annotations

from liehu.auth import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME

_ADMIN = {"username": DEFAULT_ADMIN_USERNAME, "password": DEFAULT_ADMIN_PASSWORD}


def test_login_success_and_me(anon_client):
    r = anon_client.post("/api/auth/login", json=_ADMIN)
    assert r.status_code == 200
    assert r.json()["username"] == DEFAULT_ADMIN_USERNAME
    me = anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == DEFAULT_ADMIN_USERNAME
    anon_client.post("/api/auth/logout")


def test_login_wrong_password(anon_client):
    r = anon_client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert r.status_code == 401


def test_unauthorized_returns_401(anon_client):
    """未登录访问业务接口应 401。"""
    anon_client.post("/api/auth/logout")  # 确保无会话
    assert anon_client.get("/api/stats").status_code == 401
    assert anon_client.get("/api/frontends").status_code == 401
    assert anon_client.get("/api/auth/me").status_code == 401


def test_page_guard_redirects_to_login(anon_client):
    """未登录访问 / 应 302 跳转 /login。"""
    anon_client.post("/api/auth/logout")
    r = anon_client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"


def test_change_password_invalidates_old(client):
    """改密码后旧密码失效、新密码可用; 结束时复位为默认密码。"""
    new_pw = "s3cret!"
    r = client.put(
        "/api/profile/password",
        json={"old_password": DEFAULT_ADMIN_PASSWORD, "new_password": new_pw},
    )
    assert r.status_code == 200

    # 旧密码登录失败
    bad = client.post("/api/auth/login", json=_ADMIN)
    assert bad.status_code == 401
    # 新密码登录成功
    ok = client.post(
        "/api/auth/login",
        json={"username": DEFAULT_ADMIN_USERNAME, "password": new_pw},
    )
    assert ok.status_code == 200

    # 复位为默认密码, 避免影响其他测试
    reset = client.put(
        "/api/profile/password",
        json={"old_password": new_pw, "new_password": DEFAULT_ADMIN_PASSWORD},
    )
    assert reset.status_code == 200


def test_wrong_old_password_rejected(client):
    r = client.put(
        "/api/profile/password",
        json={"old_password": "nope", "new_password": "whatever"},
    )
    assert r.status_code == 403


def test_apikeys_saved_and_masked(client):
    """保存 API 密钥后, GET 应返回掩码 (仅末 4 位可见) 且模式生效。"""
    r = client.put(
        "/api/settings/apikeys",
        json={
            "modes": {"urlscan": "live"},
            "api_keys": {"urlscan": "ABCD1234SECRET"},
        },
    )
    assert r.status_code == 200

    got = client.get("/api/settings/apikeys")
    assert got.status_code == 200
    data = got.json()
    assert data["modes"]["urlscan"] == "live"
    key_info = data["api_keys"]["urlscan"]
    assert key_info["set"] is True
    # 掩码: 仅保留末 4 位, 其余以圆点遮蔽; 明文不应出现
    assert key_info["masked"].endswith("CRET")
    assert "ABCD1234" not in key_info["masked"]

    # 复位为 mock, 清空密钥, 避免影响其他测试
    client.put(
        "/api/settings/apikeys",
        json={"modes": {"urlscan": "mock"}, "api_keys": {"urlscan": ""}},
    )
