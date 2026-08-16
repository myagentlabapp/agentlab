"""proxy.py v5: 平台认证只认 cookie(Authorization 透传给租户容器)

v6 变更(2026-08-15, F1b):
- WS 转发: 上游 Host 头改为租户原始 Host(浏览器 Host), 不再用默认的 127.0.0.1:port。
  原因: hermes 容器 socket.io 的 allowRequest 用 Jv(Origin, req.headers.host, corsOrigins)
  做同源校验 —— 当 CORS_ORIGINS 未配置(默认 "")时, 退化为"Origin 的 host 必须等于
  请求 Host 头的 host"。proxy 转发到 ws://127.0.0.1:port 时 websockets 库默认发
  Host: 127.0.0.1:port, 而浏览器 Origin=https://<租户域名>, host 不等
  -> 上游 socket.io 返回 400 "origin not allowed", WS 握手失败, 前端 socket.io 一直
  timeout。把上游 Host 改成租户域名后 Origin 与 Host 同源, 校验通过 -> 101 握手成功。

v5 变更(2026-08-15):
- check_auth_headers / _token_from: 平台 JWT 只从 cookie 读取。
  Authorization 头不再被平台校验拦截, 原样透传给租户容器 —
  因为 hermes/lobechat 等租户前端用自己的 Bearer token 调自己的 API,
  若 proxy 把 Authorization 当平台 JWT 校验会误杀 (403 登录无效或已过期)。
- WebSocket 认证同步改为只认 cookie。

v4 变更:
- 新增 @app.websocket 路由: 客户端 Upgrade 请求 -> JWT 校验(与 HTTP 相同) ->
  websockets.connect 连上游容器 -> 双向消息转发
- HTTP 转发逻辑与 v3 完全一致(不变)
"""
import os
import sqlite3
import time
from urllib.parse import quote

import httpx
import jwt
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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
    env = _load_env()
    return env.get("JWT_SECRET", "") or None


JWT_SECRET = _load_jwt_secret()

app = FastAPI(title="agent-proxy")
client = httpx.AsyncClient(timeout=120.0)

DROP_RESPONSE_HEADERS = {
    "content-length", "transfer-encoding", "connection", "content-encoding",
    "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
    "trailers", "upgrade",
}


def find_lease(prefix: str):
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


def _token_from(headers) -> str | None:
    """平台 JWT 只从 cookie 读取(v5)。

    租户容器(hermes/lobechat)自己的前端用 Authorization: Bearer <自己的token>
    调自己的 API; 若这里把 Authorization 当平台 JWT, 会 decode 失败误杀请求。
    Authorization 头原样透传, 不参与平台认证。
    """
    cookie = headers.get("cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(COOKIE_NAME + "="):
            return part[len(COOKIE_NAME) + 1:]
    return None


def decode_token(token: str):
    if not JWT_SECRET:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None


def check_auth_headers(headers) -> str | None:
    """基于请求头做认证+归属校验(HTTP 与 WebSocket 共用)。返回 None=通过。"""
    token = _token_from(headers)
    if not token:
        return "未登录"
    payload = decode_token(token)
    if not payload:
        return "登录无效或已过期"
    if payload.get("admin"):
        return None
    host = headers.get("host", "")
    prefix = extract_prefix(host)
    if prefix:
        lease = find_lease(prefix)
        if lease and payload.get("sub") != lease.get("user_id"):
            return "无权访问该实例"
    return None


@app.get("/__proxy_health")
async def health():
    return {"status": "ok", "jwt_secret_loaded": bool(JWT_SECRET), "platform_domain": PLATFORM_DOMAIN}


@app.websocket("/{path:path}")
async def proxy_ws(websocket: WebSocket, path: str):
    """WebSocket 双向转发: 浏览器 <-> proxy <-> 容器 (openclaw Gateway / hermes chat)"""
    host = websocket.headers.get("host", "")
    prefix = extract_prefix(host)
    if prefix is None:
        await websocket.close(code=4404)
        return
    lease = find_lease(prefix)
    if lease is None:
        await websocket.close(code=4404)
        return

    auth_err = check_auth_headers(websocket.headers)
    if auth_err:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    port = lease["port"]
    upstream_url = f"ws://127.0.0.1:{port}/" + path
    if websocket.query_params:
        qs = "&".join(f"{k}={v}" for k, v in websocket.query_params.items())
        upstream_url += "?" + qs

    import asyncio
    import websockets as ws_lib

    # 转发客户端 Origin 头(openclaw 按 gateway.controlUi.allowedOrigins 校验来源)
    upstream_headers = {}
    origin = websocket.headers.get("origin", "")
    if origin:
        upstream_headers["Origin"] = origin

    # 上游 Host 头用租户原始 Host(浏览器看到的域名), 不能用 127.0.0.1:port。
    # hermes socket.io 的 allowRequest(Jv) 在 CORS_ORIGINS 未配置时退化为同源校验:
    # 要求 Origin 的 host === 请求 Host 头的 host。若用默认 Host=127.0.0.1:port,
    # 浏览器 Origin=<租户域名> 与之不等 -> 上游 400 "origin not allowed", WS 握手失败。
    # 用租户域名作 Host 后两者同源, 校验通过。(v6/F1b)
    original_host = websocket.headers.get("host", "")
    if original_host:
        upstream_headers["Host"] = original_host

    try:
        upstream = await ws_lib.connect(upstream_url, open_timeout=15, additional_headers=upstream_headers)
    except Exception:
        await websocket.close(code=4402)
        return

    async def client_to_upstream():
        try:
            while True:
                msg = await websocket.receive()
                t = msg.get("type")
                if t == "websocket.receive":
                    if msg.get("bytes") is not None:
                        await upstream.send(msg["bytes"])
                    elif msg.get("text") is not None:
                        await upstream.send(msg["text"])
                elif t == "websocket.disconnect":
                    break
        except Exception:
            pass
        finally:
            try:
                await upstream.close()
            except Exception:
                pass

    async def upstream_to_client():
        try:
            async for m in upstream:
                if isinstance(m, str):
                    await websocket.send_text(m)
                else:
                    await websocket.send_bytes(m)
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    t1 = asyncio.create_task(client_to_upstream())
    t2 = asyncio.create_task(upstream_to_client())
    done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request):
    host = request.headers.get("host", "")
    prefix = extract_prefix(host)
    if prefix is None:
        return JSONResponse({"detail": "unknown host: " + host}, status_code=404)

    lease = find_lease(prefix)
    if lease is None:
        return JSONResponse({"detail": f"lease '{prefix}' not found or not running"}, status_code=404)

    auth_err = check_auth_headers(request.headers)
    if auth_err == "未登录":
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
    # 上游 Host 用租户原始 Host, 与 WS 转发同理(v6/F1b): hermes socket.io 的同源校验
    # (allowRequest / @koa/cors) 要求 Origin.host === 请求 Host.host。httpx 默认会按
    # url(127.0.0.1:port) 设置 Host, 这里显式覆盖为租户域名, 使 Origin 与 Host 同源。
    if host:
        headers["host"] = host
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
