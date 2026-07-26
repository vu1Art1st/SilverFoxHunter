"""鉴权基础设施 (仅标准库)。

职责:
    - 密码哈希: pbkdf2_hmac(sha256) + 每用户随机盐;
    - 会话令牌: hmac 签名的 Cookie (user_id.issued_ts.signature);
    - 应用密钥 SECRET: 读环境变量, 缺省则随机生成并持久化到 app_settings;
    - FastAPI 依赖 require_user: 校验 Cookie, 失败抛 401。

设计取舍: 单机自用、单管理员, 不引入 bcrypt/JWT 等第三方库, 全部用标准库实现,
保持项目"零外部鉴权依赖"的极简风格。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timezone

from fastapi import Cookie, HTTPException, status

from .db import get_connection, row_to_dict

# ---- 常量 --------------------------------------------------------------------

COOKIE_NAME = "sfh_session"
SESSION_MAX_AGE = 7 * 24 * 3600  # 7 天
_PBKDF2_ROUNDS = 200_000
_SECRET_KEY = "session_secret"  # app_settings 中的键名


# ---- 密码哈希 ----------------------------------------------------------------

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """返回 (salt_hex, hash_hex)。salt 缺省时随机生成。"""
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, _PBKDF2_ROUNDS
    )
    return salt_bytes.hex(), dk.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """校验明文密码是否匹配存储的盐与哈希 (常数时间比较)。"""
    _, calc = hash_password(password, salt_hex)
    return hmac.compare_digest(calc, hash_hex)


# ---- 应用密钥 (会话签名) ------------------------------------------------------

def get_secret() -> bytes:
    """获取会话签名密钥。

    优先读环境变量 LIEHU_SECRET; 否则从 app_settings 读取, 若无则随机生成并持久化,
    保证进程重启后已签发的会话仍然有效。
    """
    env = os.getenv("LIEHU_SECRET")
    if env:
        return env.encode("utf-8")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (_SECRET_KEY,)
        ).fetchone()
        if row and row["value"]:
            return row["value"].encode("utf-8")
        generated = secrets.token_hex(32)
        conn.execute(
            "INSERT OR REPLACE INTO app_settings(key, value) VALUES (?, ?)",
            (_SECRET_KEY, generated),
        )
        conn.commit()
        return generated.encode("utf-8")
    finally:
        conn.close()


# ---- 会话令牌 ----------------------------------------------------------------

def _sign(payload: str) -> str:
    sig = hmac.new(get_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def issue_session(user_id: int) -> str:
    """签发会话令牌: base64(user_id.issued_ts).signature。"""
    payload = f"{user_id}.{int(time.time())}"
    token = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{token}.{_sign(payload)}"


def _b64decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def parse_session(token: str | None) -> int | None:
    """校验会话令牌并返回 user_id; 无效或过期返回 None。"""
    if not token or token.count(".") != 1:
        return None
    token_part, sig = token.split(".", 1)
    try:
        payload = _b64decode(token_part).decode("utf-8")
    except Exception:
        return None
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    try:
        uid_str, issued_str = payload.split(".", 1)
        uid, issued = int(uid_str), int(issued_str)
    except ValueError:
        return None
    if time.time() - issued > SESSION_MAX_AGE:
        return None
    return uid


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, avatar, created_at, updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def ensure_default_admin() -> None:
    """若 users 表为空, 种子默认管理员 admin/admin。

    独立于业务种子回放, 保证首次启动即可登录。
    """
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count > 0:
            return
        salt, pw_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users(username, pw_salt, pw_hash, avatar, created_at, updated_at) "
            "VALUES (?, ?, ?, NULL, ?, ?)",
            (DEFAULT_ADMIN_USERNAME, salt, pw_hash, now, now),
        )
        conn.commit()
    finally:
        conn.close()


# ---- FastAPI 依赖 ------------------------------------------------------------

def current_user_id(session_token: str | None) -> int | None:
    """从 Cookie 值解析出有效 user_id (供服务端页面守卫复用)。"""
    return parse_session(session_token)


def require_user(sfh_session: str | None = Cookie(default=None)) -> dict:
    """受保护路由依赖: 未登录或会话失效抛 401。"""
    uid = parse_session(sfh_session)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或会话已失效"
        )
    user = get_user_by_id(uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在"
        )
    return user
