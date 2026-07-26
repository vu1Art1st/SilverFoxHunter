"""鉴权路由: 登录 / 登出 / 当前用户。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from ..auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    issue_session,
    require_user,
    verify_password,
)
from ..db import get_connection

router = APIRouter(tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginBody, response: Response) -> dict:
    """校验用户名/密码, 成功则下发签名会话 Cookie。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, pw_salt, pw_hash FROM users WHERE username = ?",
            (body.username,),
        ).fetchone()
    finally:
        conn.close()

    if row is None or not verify_password(body.password, row["pw_salt"], row["pw_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    token = issue_session(row["id"])
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "username": row["username"]}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    """清除会话 Cookie。"""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: dict = Depends(require_user)) -> dict:
    """返回当前登录用户 (未登录由 require_user 抛 401)。"""
    return {"id": user["id"], "username": user["username"], "avatar": user.get("avatar")}
