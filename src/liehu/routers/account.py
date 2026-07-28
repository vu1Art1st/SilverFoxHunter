"""个人中心路由: 修改用户名 / 密码 / 头像, 以及 API 密钥配置。

所有接口均需登录 (require_user)。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import hash_password, require_user, verify_password
from ..config import (
    API_KEY_COLLECTORS,
    MODE_COLLECTORS,
    parse_api_keys,
    save_overrides_to_db,
    settings,
)
from ..db import get_connection

router = APIRouter(tags=["account"])

# 头像 dataURL 上限 ~512KB (base64 后约 700KB, 留余量)
_AVATAR_MAX_LEN = 700_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/profile")
def get_profile(user: dict = Depends(require_user)) -> dict:
    """当前用户资料 (用户名 + 头像)。"""
    return {
        "username": user["username"],
        "avatar": user.get("avatar"),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


class UsernameBody(BaseModel):
    username: str


@router.put("/profile/username")
def update_username(body: UsernameBody, user: dict = Depends(require_user)) -> dict:
    """修改用户名 (唯一约束)。"""
    new_name = body.username.strip()
    if not new_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名不能为空")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET username = ?, updated_at = ? WHERE id = ?",
            (new_name, _now(), user["id"]),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")
    finally:
        conn.close()
    return {"ok": True, "username": new_name}


class PasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.put("/profile/password")
def update_password(body: PasswordBody, user: dict = Depends(require_user)) -> dict:
    """修改密码 (需校验旧密码)。"""
    if len(body.new_password) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码至少 4 位")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT pw_salt, pw_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if row is None or not verify_password(
            body.old_password, row["pw_salt"], row["pw_hash"]
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "旧密码错误")
        salt, pw_hash = hash_password(body.new_password)
        conn.execute(
            "UPDATE users SET pw_salt = ?, pw_hash = ?, updated_at = ? WHERE id = ?",
            (salt, pw_hash, _now(), user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


class AvatarBody(BaseModel):
    avatar: str  # base64 dataURL, 如 data:image/png;base64,...


@router.put("/profile/avatar")
def update_avatar(body: AvatarBody, user: dict = Depends(require_user)) -> dict:
    """更新头像 (base64 dataURL)。"""
    avatar = body.avatar.strip()
    if avatar and not avatar.startswith("data:image/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "头像需为图片 dataURL")
    if len(avatar) > _AVATAR_MAX_LEN:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "头像过大 (>512KB)")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET avatar = ?, updated_at = ? WHERE id = ?",
            (avatar or None, _now(), user["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


def _mask(key: str | None) -> str:
    """掩码显示 API 密钥, 只保留末 4 位。"""
    if not key:
        return ""
    if len(key) <= 4:
        return "•" * len(key)
    return "•" * (len(key) - 4) + key[-4:]


def _mask_multi(raw: str | None) -> str:
    """掩码显示多 KEY 配置 (threatbook 等): 逐个掩码, 标注数量。"""
    keys = parse_api_keys(raw)
    if not keys:
        return ""
    masked = ", ".join(_mask(k)[-8:] for k in keys)
    return f"{len(keys)} 个: {masked}"


@router.get("/settings/apikeys")
def get_apikeys(user: dict = Depends(require_user)) -> dict:
    """返回各采集器模式与 API 密钥 (密钥掩码显示, 多 KEY 逐个掩码)。"""
    modes = {name: getattr(settings, name).mode for name in MODE_COLLECTORS}
    keys = {}
    for name in API_KEY_COLLECTORS:
        raw = getattr(settings, name).api_key
        multi = len(parse_api_keys(raw)) > 1
        keys[name] = {
            "masked": _mask_multi(raw) if multi else _mask(raw),
            "set": bool(raw),
        }
    return {"modes": modes, "api_keys": keys}


class ApiKeysBody(BaseModel):
    modes: dict[str, str] = {}
    api_keys: dict[str, str] = {}


@router.put("/settings/apikeys")
def update_apikeys(body: ApiKeysBody, user: dict = Depends(require_user)) -> dict:
    """保存采集器模式与 API 密钥并即时生效。

    api_keys 中值为空字符串表示清除该密钥; 未提供的键保持不变。
    """
    # 仅对提供了非 None 值的键做更新
    keys_to_save = {k: v for k, v in body.api_keys.items() if v is not None}
    save_overrides_to_db(body.modes, keys_to_save)
    return get_apikeys(user)
