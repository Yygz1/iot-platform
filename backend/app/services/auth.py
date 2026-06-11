"""JWT 认证服务"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import Request, HTTPException
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# 配置（从环境变量读取，开发环境自动生成随机密钥）
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("JWT_SECRET_KEY 未设置，已生成随机密钥（重启后失效，生产环境请设置环境变量）")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 哈希密码（安全、内置、无外部依赖）"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码（支持 PBKDF2 和旧的 SHA256 格式）"""
    if "$" in hashed_password:
        # PBKDF2 格式: salt$hash
        salt, stored_hash = hashed_password.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 100000)
        return dk.hex() == stored_hash
    else:
        # 兼容旧的 SHA256 格式（迁移用）
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def create_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"user_id": int(payload["sub"]), "username": payload["username"]}
    except JWTError:
        return None


# 白名单路径（不需要认证）
WHITELIST_PATHS = {
    "/",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/check",
    "/api/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def is_whitelisted(path: str, method: str) -> bool:
    """检查路径是否在白名单中"""
    if path in WHITELIST_PATHS:
        return True
    if path.startswith("/api/auth/"):
        return True
    # 设备查询（模拟器/SDK 检查设备是否存在）
    if method == "GET" and path.startswith("/api/devices/"):
        return True
    if path.startswith("/api/docs"):
        return True
    # 设备上报接口（模拟器用）
    if method == "PUT" and "/shadow/reported" in path:
        return True
    return False


async def get_current_user(request: Request) -> dict:
    """从请求中提取当前用户（FastAPI 依赖注入）"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    token = auth_header[7:]
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")

    return user
