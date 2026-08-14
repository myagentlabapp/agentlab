"""Auth routes: 注册/登录/me + JWT 工具（v2：登录/注册响应 Set-Cookie，租户子域名共享登录态）"""

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

from app_secrets import JWT_SECRET

SECRET = JWT_SECRET
ALGO = "HS256"

# 平台登录 cookie：Domain=.myagentlab.homes 使所有租户子域名共享
COOKIE_NAME = "myagentlab_token"
COOKIE_DOMAIN = ".myagentlab.homes"


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


def hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def create_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "admin": bool(user.is_admin),
        "exp": int(time.time()) + 7 * 24 * 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效登录")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def get_admin_user(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def _auth_response(user: User):
    """登录/注册成功响应：JSON + Set-Cookie（HttpOnly，租户子域名共享）"""
    token = create_token(user)
    resp = JSONResponse({
        "token": token,
        "username": user.username,
        "is_admin": bool(user.is_admin),
    })
    resp.set_cookie(
        COOKIE_NAME,
        token,
        max_age=7 * 24 * 3600,
        httponly=True,
        domain=COOKIE_DOMAIN,
        path="/",
        samesite="lax",
        secure=True,
    )
    return resp


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    from settings_store import get_setting
    if get_setting("registration_open", "true") != "true":
        raise HTTPException(status_code=403, detail="注册已关闭")
    if len(req.username) < 2 or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="用户名至少 2 位，密码至少 6 位")
    exists = db.query(User).filter(User.username == req.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        id=str(uuid.uuid4()),
        username=req.username,
        password_hash=hash_password(req.password),
        is_admin=0,
    )
    db.add(user)
    db.commit()
    return _auth_response(user)


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not getattr(user, "enabled", 1):
        raise HTTPException(status_code=403, detail="账号已禁用")
    return _auth_response(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "is_admin": bool(user.is_admin)}


@router.post("/logout")
def logout():
    resp = JSONResponse({"success": True})
    resp.delete_cookie(COOKIE_NAME, domain=COOKIE_DOMAIN, path="/")
    return resp
