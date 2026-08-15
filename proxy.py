"""Agent 实例动态反向代理：Host 子域名 -> 查库拿端口 -> JWT 校验 -> 转发到本地容器端口
支持两种域名格式：
  {lease_prefix}.{platform_domain}            (一级子域，证书免费覆盖)
  {lease_prefix}.agent.{platform_domain}      (兼容旧格式)

platform_domain 从 DB settings 表读取（后台可配置），未配置时回退 .env PLATFORM_DOMAIN。

v3 安全：JWT 认证 + 归属校验
  - 请求必须带平台登录 token（Cookie myagentlab_token 或 Authorization Bearer）
  - token 无效/过期 -> 302 重定向到平台登录页（带 redirect 回跳）
  - token 有效但子域名不属于当前用户 -> 403
  - 管理员 token 可访问任意子域名（调试/运维）

v2 修复：httpx 转发时自动解压了响应 body，但保留的 content-encoding 头
会让浏览器按原编码解码失败（ERR_CONTENT_DECODING_FAILED）。
转发时移除 content-encoding / content-length 头，让下游（CF/浏览器）重新压缩。
"""
import os
import sqlite3
import time
from urllib.parse import quote

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse, RedirectResponse

_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_ROOT, "backend", "data.db")
ENV_FILE = os.path.join(_ROOT, "backend", ".env")
COOKIE_NAME = "myagentlab_token"
JWT_ALGO = "HS256"


def _load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def _load_platform_conf():
    """从 DB settings 读 platform_domain / platform_url，回退 .env"""
    env = _load_env()
    domain = env.get("PLATFORM_DOMAIN", "")
    url = env.get("PLATFORM_URL", "")
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = dict(conn.execute("SELECT key, value FROM settings WHERE key IN ('platform_domain','platform_url')").fetchall())
        conn.close()
        domain = rows.get("platform_domain") or domain
        url = rows.get("platform_url") or url
    except Exception:
        pass
    return domain.strip(), url.strip()


PLATFORM_DOMAIN, PLATFORM_URL = _load_platform_conf()
LOGIN_URL = (PLATFORM_URL or f"https://agent.{PLATFORM_DOMAIN}" if PLATFORM_DOMAIN else "") + "/login"


def _load_jwt_secret():
    """从 backend/.env 读 JWT_SECRET（与 app_secrets 同款逻辑，proxy 独立进程）"""
    env = _load_env()
    return env.get("JWT_SECRET", "") or None


JWT_SECRET = _load_jwt_secret()

app = FastAPI(title="agent-proxy")
client = httpx.AsyncClient(timeout=120.0)

# 转发时必须剔除的响应头（httpx 已解码 body，头不匹配会解码失败）
DROP_RESPONSE_HEADERS = {
    "content-length",
    "transfer-encoding",
    "connection",
    "content-encoding",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
}


def find_lease(prefix: str):
    """按 lease_id 前缀查 lease，返回 {id, port, user_id, status}"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, port, status, user_id FROM leases WHERE id LIKE ?",
            (prefix + "%",)
        ).fetchall()
        conn.close()
        for r in rows:
            if r["status"] == "running":
                return dict(r)
        return dict(rows[0]) if rows else None
    except Exception:
        return None


def extract_prefix(host: str) -> str | None:
    """从 Host 头提取 lease 前缀"""
    if not PLATFORM_DOMAIN:
        return None
    host = host.split(":")[0]
    suffix = "." + PLATFORM_DOMAIN
    if host.endswith(suffix):
        sub = host[: -len(suffix)]
        if sub and "." not in sub:
            return sub
    legacy_suffix = ".agent." + PLATFORM_DOMAIN
    if host.endswith(legacy_suffix):
        sub = host[: -len(legacy_suffix)]
        if sub and "." not in sub:
            return sub
    return None


def get_token(request: Request) -> str | None:
    """从 Cookie 或 Authorization 头取 token"""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get(COOKIE_NAME)


def decode_token(token: str):
    """校验 JWT，返回 payload 或 None"""
    if not JWT_SECRET:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None


def check_auth(request: Request, lease: dict) -> str | None:
    """认证 + 归属校验。返回 None=通过，否则返回错误描述。"""
    token = get_token(request)
    if not token:
        return "未登录"
    payload = decode_token(token)
    if not payload:
        return "登录无效或已过期"
    if payload.get("admin"):
        return None  # 管理员可访问任意实例
    if lease and payload.get("sub") != lease.get("user_id"):
        return "无权访问该实例"
    return None




@app.get("/__proxy_health")
async def health():
    return {"status": "ok", "jwt_secret_loaded": bool(JWT_SECRET), "platform_domain": PLATFORM_DOMAIN}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request):
    host = request.headers.get("host", "")
    prefix = extract_prefix(host)
    if prefix is None:
        return JSONResponse({"detail": "unknown host: " + host}, status_code=404)

    lease = find_lease(prefix)
    if lease is None:
        return JSONResponse({"detail": f"lease '{prefix}' not found or not running"}, status_code=404)

    # ---- v3 安全：认证 + 归属 ----
    auth_err = check_auth(request, lease)
    if auth_err == "未登录":
        # 浏览器请求 -> 302 跳登录页；API 请求 -> 401 JSON
        target = f"https://{host}/" + path
        if request.url.query:
            target += "?" + request.url.query
        if request.headers.get("accept", "").find("text/html") >= 0:
            return RedirectResponse(
                f"{LOGIN_URL}?redirect={quote(target, safe='')}",
                status_code=302,
            )
        return JSONResponse({"detail": "未登录"}, status_code=401)
    if auth_err:
        return JSONResponse({"detail": auth_err}, status_code=403)

    port = lease["port"]
    url = f"http://127.0.0.1:{port}/" + path
    if request.url.query:
        url += "?" + request.url.query

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "connection", "transfer-encoding", "accept-encoding", "cookie")
    }
    body = await request.body()
    try:
        resp = await client.request(
            request.method, url, headers=headers, content=body or None,
        )
        out_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in DROP_RESPONSE_HEADERS
        }
        return Response(content=resp.content, status_code=resp.status_code, headers=out_headers)
    except httpx.HTTPError:
        return JSONResponse({"detail": "upstream error"}, status_code=502)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
