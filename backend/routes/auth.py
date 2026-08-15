"""Auth routes: 注册/登录/me + JWT 工具（v4：Turnstile 人机验证 + 登录限流 + 失败锁定）"""

import hashlib
import hmac
import json
import secrets
import threading
import time
import urllib.request
import uuid
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

from app_secrets import JWT_SECRET

SECRET = JWT_SECRET
ALGO = "HS256"

# 平台登录 cookie：Domain 动态取 settings.platform_domain（所有租户子域名共享）
COOKIE_NAME = "myagentlab_token"
COOKIE_DOMAIN = None

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


# ============================================================
# 内存限流器（每 IP 滑动窗口）+ 失败锁定（每用户名）
# ============================================================
class SlidingWindowLimiter:
    """每 key 滑动窗口限流（线程安全，内存存储）"""

    def __init__(self):
        self._hits = {}          # key -> [timestamps]
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: int) -> bool:
        now = time.time()
        with self._lock:
            hits = self._hits.get(key, [])
            hits = [t for t in hits if now - t < window_s]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            # 顺手清理过期 key（防内存膨胀）
            if len(self._hits) > 10000:
                cutoff = now - max(window_s, 3600)
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > cutoff}
            return True


class LoginLockout:
    """登录失败锁定：每用户名连续失败 N 次 → 锁 M 分钟"""

    def __init__(self):
        self._fails = {}         # username -> (count, last_ts, locked_until)
        self._lock = threading.Lock()

    def check(self, username: str, threshold: int, lock_minutes: int) -> tuple[bool, int]:
        """返回 (是否允许尝试, 剩余锁定秒数)"""
        with self._lock:
            rec = self._fails.get(username)
            if not rec:
                return True, 0
            count, last_ts, locked_until = rec
            now = time.time()
            if locked_until and now < locked_until:
                return False, int(locked_until - now)
            return True, 0

    def record_fail(self, username: str, threshold: int, lock_minutes: int) -> int:
        """记录一次失败。返回锁定剩余秒数（0=未触发锁定）"""
        with self._lock:
            now = time.time()
            count, last_ts, locked_until = self._fails.get(username, (0, 0, 0))
            # 失败间隔超过 30 分钟 → 重新计数
            if now - last_ts > 1800:
                count = 0
            count += 1
            if count >= threshold:
                locked_until = now + lock_minutes * 60
                self._fails[username] = (0, now, locked_until)
                return int(locked_until - now)
            self._fails[username] = (count, now, 0)
            return 0

    def reset(self, username: str):
        with self._lock:
            self._fails.pop(username, None)


_login_limiter = SlidingWindowLimiter()
_register_limiter = SlidingWindowLimiter()
_login_lockout = LoginLockout()


def _get_client_ip(request: Request) -> str:
    """取真实客户端 IP（CF Tunnel 场景优先 X-Forwarded-For）"""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _verify_turnstile(token: str, secret: str, ip: str = "") -> bool:
    """调 Cloudflare siteverify 验证 token"""
    if not secret:
        return False
    data = urllib.parse.urlencode({"secret": secret, "response": token, "remoteip": ip}).encode()
    try:
        req = urllib.request.Request(TURNSTILE_VERIFY_URL, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return bool(result.get("success"))
    except Exception:
        return False


class RegisterRequest(BaseModel):
    username: str
    password: str
    turnstile_token: str = ""
    email: str = ""
    code: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str
    turnstile_token: str = ""


class ForgotPasswordRequest(BaseModel):
    username: str
    turnstile_token: str = ""


class ResetPasswordRequest(BaseModel):
    username: str
    email: str
    code: str
    new_password: str


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
        "balance": round(getattr(user, "balance", 0) or 0, 2),
    })
    from settings_store import get_setting
    _pd = (get_setting("platform_domain", "") or "").strip()
    resp.set_cookie(
        COOKIE_NAME,
        token,
        max_age=7 * 24 * 3600,
        httponly=True,
        domain=("." + _pd) if _pd else None,
        path="/",
        samesite="lax",
        secure=True,
    )
    return resp




@router.post("/send-code")
def send_code(request: Request, body: dict = None):
    """发送邮箱验证码（注册用）"""
    from settings_store import get_setting
    from email_service import send_code as _send_code
    import re as _re

    email = (body or {}).get("email", "").strip()
    if not email or not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="请输入正确的邮箱")

    # 限流（复用注册限流器）
    ip = _get_client_ip(request)
    if not _register_limiter.allow(f"code:{ip}", 5, 60):
        raise HTTPException(status_code=429, detail="操作太频繁，请 1 分钟后再试")

    if get_setting("email_register_enabled", "false") != "true":
        raise HTTPException(status_code=403, detail="邮箱注册未开启")

    ok, msg = _send_code(email)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": "验证码已发送"}


@router.post("/register")
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    from settings_store import get_setting
    ldap_enabled = get_setting("lldap_enabled", "false") == "true"
    if ldap_enabled:
        # LLDAP 统一认证模式：允许注册，但在 LLDAP 中创建用户（代理注册）
        # 仍需邮箱验证码 + Turnstile + 限流
        pass
    ip = _get_client_ip(request)

    # ---- 1. 注册限流：每 IP 每分钟 5 次 ----
    if not _register_limiter.allow(f"reg:{ip}", 5, 60):
        raise HTTPException(status_code=429, detail="注册太频繁，请 1 分钟后再试")

    if get_setting("registration_open", "true") != "true":
        raise HTTPException(status_code=403, detail="注册已关闭")

    # ---- 2. Turnstile 人机验证（后台开启时校验） ----
    ts_enabled = get_setting("turnstile_enabled", "false") == "true"
    if ts_enabled:
        ts_secret = get_setting("turnstile_secret_key", "")
        if not _verify_turnstile(req.turnstile_token, ts_secret, ip):
            raise HTTPException(status_code=403, detail="人机验证未通过，请重试")

    # ---- 3.5 邮箱验证码校验（开启时必填）----
    email_enabled = get_setting("email_register_enabled", "false") == "true"
    if email_enabled:
        import re as _re
        if not req.email or not _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", req.email):
            raise HTTPException(status_code=400, detail="请输入正确的邮箱")
        if not req.code:
            raise HTTPException(status_code=400, detail="请输入邮箱验证码")
        from email_service import verify_code
        ok, msg = verify_code(req.email, req.code)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

    if len(req.username) < 2 or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="用户名至少 2 位，密码至少 6 位")
    exists = db.query(User).filter(User.username == req.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    if ldap_enabled:
        # LLDAP 模式：在 LLDAP 中创建用户，本地建影子账号
        from ldap_auth import ldap_create_user
        ok, ldap_err = ldap_create_user(req.username, req.password, req.email if email_enabled else "")
        if not ok:
            raise HTTPException(status_code=500, detail="LDAP 用户创建失败: " + ldap_err)
        user = User(
            id=str(uuid.uuid4()),
            username=req.username,
            password_hash="",
            is_admin=0,
            email=req.email if email_enabled else "",
        )
        db.add(user)
        db.commit()
        return _auth_response(user)

    user = User(
        id=str(uuid.uuid4()),
        username=req.username,
        password_hash=hash_password(req.password),
        is_admin=0,
        email=req.email if email_enabled else "",
    )
    db.add(user)
    db.commit()
    return _auth_response(user)


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    from settings_store import get_setting
    ip = _get_client_ip(request)

    # ---- 1. 登录限流：每 IP 每分钟 N 次 ----
    rate_limit = int(get_setting("login_rate_limit", "10") or 10)
    if not _login_limiter.allow(f"login:{ip}", rate_limit, 60):
        raise HTTPException(status_code=429, detail="尝试太频繁，请 1 分钟后再试")

    # ---- 2. 失败锁定：连续失败 N 次锁 M 分钟 ----
    threshold = int(get_setting("login_lockout_threshold", "5") or 5)
    lock_minutes = int(get_setting("login_lockout_minutes", "15") or 15)
    allowed, wait_s = _login_lockout.check(req.username, threshold, lock_minutes)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"账号已锁定，请 {max(wait_s // 60, 1)} 分钟后再试",
        )

    # ---- 3. Turnstile（登录也校验，防撞库）----
    ts_enabled = get_setting("turnstile_enabled", "false") == "true"
    if ts_enabled:
        ts_secret = get_setting("turnstile_secret_key", "")
        if not _verify_turnstile(req.turnstile_token, ts_secret, ip):
            raise HTTPException(status_code=403, detail="人机验证未通过，请重试")

    # ---- 4. 认证（互斥模式）----
    ldap_enabled = get_setting("lldap_enabled", "false") == "true"
    user = db.query(User).filter(User.username == req.username).first()

    # admin 账号永远走本地密码，防止开了 LDAP 把后台锁死
    if user and user.username == "admin" and user.password_hash and verify_password(req.password, user.password_hash):
        _login_lockout.reset(req.username)
        return _auth_response(user)

    if ldap_enabled:
        # LLDAP 开启：只走 LLDAP，本地密码登录禁用
        try:
            from ldap_auth import ldap_authenticate
            ldap_user = ldap_authenticate(req.username, req.password)
            if ldap_user:
                if not user:
                    user = User(
                        id=str(uuid.uuid4()),
                        username=ldap_user["username"],
                        password_hash="",
                        is_admin=1 if ldap_user["is_admin"] else 0,
                        email=ldap_user.get("email", ""),
                    )
                    db.add(user)
                    db.commit()
                else:
                    if user.is_admin != (1 if ldap_user["is_admin"] else 0):
                        user.is_admin = 1 if ldap_user["is_admin"] else 0
                        user.email = ldap_user.get("email", user.email or "")
                        db.commit()
                _login_lockout.reset(req.username)
                return _auth_response(user)
        except ImportError:
            pass
        except Exception:
            pass
    else:
        # LLDAP 关闭：只走本地密码验证
        if user and user.password_hash and verify_password(req.password, user.password_hash):
            _login_lockout.reset(req.username)
            return _auth_response(user)

    # 认证失败
    locked_s = _login_lockout.record_fail(req.username, threshold, lock_minutes)
    if locked_s > 0:
        raise HTTPException(
            status_code=429,
            detail=f"连续失败 {threshold} 次，账号锁定 {lock_minutes} 分钟",
        )
    remain = threshold - _login_lockout._fails.get(req.username, (0, 0, 0))[0] if req.username in _login_lockout._fails else 0
    raise HTTPException(status_code=401, detail="用户名或密码错误" + (f"（再错 {remain} 次锁定）" if remain > 0 else ""))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "balance": round(getattr(user, "balance", 0) or 0, 2),"id": user.id, "username": user.username, "is_admin": bool(user.is_admin)}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Send reset code to user's bound email"""
    from settings_store import get_setting
    from email_service import send_code as _send_code

    ip = _get_client_ip(request)
    if not _register_limiter.allow("forgot:" + ip, 5, 60):
        raise HTTPException(status_code=429, detail="操作太频繁，请 1 分钟后再试")

    user = db.query(User).filter(User.username == req.username).first()
    if not user or not user.email:
        return {"success": True, "message": "如用户存在，验证码已发送至绑定邮箱"}

    ts_enabled = get_setting("turnstile_enabled", "false") == "true"
    if ts_enabled:
        ts_secret = get_setting("turnstile_secret_key", "")
        if not _verify_turnstile(req.turnstile_token, ts_secret, ip):
            raise HTTPException(status_code=403, detail="人机验证未通过")

    ok, msg = _send_code(user.email, purpose="reset")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    at = user.email.find("@")
    hint = user.email[:2] + "***" + user.email[at:] if at > 0 else user.email
    return {"success": True, "message": "验证码已发送", "email_hint": hint}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Verify code and reset password"""
    from settings_store import get_setting
    from email_service import verify_code

    ip = _get_client_ip(request)
    if not _register_limiter.allow("reset:" + ip, 5, 60):
        raise HTTPException(status_code=429, detail="操作太频繁，请 1 分钟后再试")

    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    if user.email != req.email:
        raise HTTPException(status_code=400, detail="邮箱与用户不匹配")

    ok, msg = verify_code(req.email, req.code, purpose="reset")
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    ldap_enabled = get_setting("lldap_enabled", "false") == "true"
    if ldap_enabled and user.username != "admin":
        import subprocess
        url = get_setting("lldap_url", "")
        bind_dn = get_setting("lldap_bind_dn", "")
        bind_password = get_setting("lldap_bind_password", "")
        base_dn = get_setting("lldap_base_dn", "")
        if url and bind_dn and base_dn:
            host_part = url.replace("ldap://", "").replace("ldaps://", "")
            ldap_uri = "ldap://" + host_part if not url.startswith("ldaps") else "ldaps://" + host_part
            user_dn = "uid=" + user.username + "," + base_dn
            try:
                r = subprocess.run(
                    ["ldappasswd", "-x", "-H", ldap_uri, "-D", bind_dn,
                     "-w", bind_password, "-s", req.new_password, user_dn],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode != 0:
                    raise HTTPException(status_code=500, detail="LDAP 密码重置失败")
            except FileNotFoundError:
                raise HTTPException(status_code=500, detail="服务器缺少 ldap-utils")
    else:
        user.password_hash = hash_password(req.new_password)
        db.commit()

    return {"success": True, "message": "密码重置成功"}


@router.post("/logout")
def logout():
    resp = JSONResponse({"success": True})
    resp.delete_cookie(COOKIE_NAME, domain=COOKIE_DOMAIN, path="/")
    return resp
