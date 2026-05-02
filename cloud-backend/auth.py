import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import requests
from jose import jwt
from fastapi import HTTPException

from config import config
from models import User

logger = logging.getLogger(__name__)

# 微信小程序配置
WECHAT_APPID = config.WECHAT_APPID
WECHAT_SECRET = config.WECHAT_SECRET
JWT_SECRET = config.JWT_SECRET
JWT_ALGORITHM = config.JWT_ALGORITHM
JWT_EXPIRE_HOURS = config.JWT_EXPIRE_HOURS

# 开发模式
DEV_MODE = os.getenv('DEV_MODE', '').lower() == 'true'

WECHAT_JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

def create_jwt_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_jwt_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None

def is_wechat_login_ready() -> bool:
    return bool(WECHAT_APPID and WECHAT_SECRET)

def get_wechat_openid(code: str) -> Optional[str]:
    if DEV_MODE:
        return "dev-user"

    if not is_wechat_login_ready():
        logger.error("WECHAT_APPID / WECHAT_SECRET not configured")
        return None

    url = f"{WECHAT_JSCODE2SESSION_URL}?appid={WECHAT_APPID}&secret={WECHAT_SECRET}&js_code={code}&grant_type=authorization_code"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("openid"):
            return data["openid"]
        logger.error(f"WeChat login failed: {data}")
        return None
    except Exception as e:
        logger.error(f"WeChat request error: {e}")
        return None

def hash_password(password: str) -> str:
    """密码加密"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def register_user(username: str, password: str, db):
    """注册新用户"""
    # 检查用户名是否已存在
    user = db.query(User).filter(User.username == username).first()
    if user:
        raise HTTPException(400, "用户名已存在")
    
    # 创建用户
    password_hash = hash_password(password)
    user = User(
        id=username,  # 使用 username 作为 id
        username=username,
        password_hash=password_hash,
        running_tasks=0,
        quota=3,
        total_generated=0,
        created_at=datetime.now(timezone.utc)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_jwt_token(user.id)
    return {
        "token": token,
        "user_id": user.id,
        "quota": user.quota,
        "message": "注册成功"
    }

def login_with_password(username: str, password: str, db):
    """密码登录"""
    # 查找用户
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.password_hash:
        raise HTTPException(401, "用户名或密码错误")
    
    # 验证密码
    if not verify_password(password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    
    token = create_jwt_token(user.id)
    return {
        "token": token,
        "user_id": user.id,
        "quota": user.quota,
        "total_generated": user.total_generated
    }

def init_user_if_not_exists(openid: str):
    # 延迟导入，避免循环依赖
    from main import SessionLocal, User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == openid).first()
        if not user:
            user = User(
                id=openid,
                running_tasks=0,
                quota=3,
                total_generated=0,
                created_at=datetime.now(timezone.utc)
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()
