"""认证 API"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import User
from app.services.auth import (
    hash_password, verify_password, create_token, get_current_user,
)
from app.services.device_shadow import _now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)


@router.post("/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    """登录获取 Token"""
    result = await session.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user.id, user.username)
    return {
        "token": token,
        "username": user.username,
        "expires_in": 86400,  # 24小时
    }


@router.post("/register")
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    """注册管理员账号（仅首次，已有用户时拒绝）"""
    # 检查是否已有用户
    count = await session.scalar(select(func.count(User.id)))
    if count and count > 0:
        raise HTTPException(status_code=403, detail="已有管理员账号，不允许重复注册")

    # 检查用户名是否已存在
    existing = await session.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_token(user.id, user.username)
    return {
        "token": token,
        "username": user.username,
        "message": "管理员账号创建成功",
    }


@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户信息"""
    user = await session.get(User, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "id": user.id,
        "username": user.username,
        "created_at": user.created_at,
    }


@router.get("/check")
async def check_users(session: AsyncSession = Depends(get_session)):
    """检查是否已有管理员账号（前端用来决定显示登录还是注册）"""
    count = await session.scalar(select(func.count(User.id)))
    return {"has_users": bool(count and count > 0)}
