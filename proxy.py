"""Agent 实例动态反向代理：Host 子域名 -> 查库拿端口 -> 转发到本地容器端口
支持两种域名格式：
  {lease_prefix}.myagentlab.homes        (一级子域，证书免费覆盖)
  {lease_prefix}.agent.myagentlab.homes  (兼容旧格式)

v2 修复：httpx 转发时自动解压了响应 body，但保留的 content-encoding 头
会让浏览器按原编码解码失败（ERR_CONTENT_DECODING_FAILED）。
转发时移除 content-encoding / content-length 头，让下游（CF/浏览器）重新压缩。
"""
import sqlite3
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse

DB_PATH = ".AGENT_PLATFORM_ROOT/backend/data.db"

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


def find_port(prefix: str):
    """按 lease_id 前缀查 running lease 的端口"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, port, status FROM leases WHERE id LIKE ?",
            (prefix + "%",)
        ).fetchall()
        conn.close()
        for r in rows:
            if r["status"] == "running":
                return r["port"]
        return rows[0]["port"] if rows else None
    except Exception:
        return None


def extract_prefix(host: str) -> str | None:
    """从 Host 头提取 lease 前缀"""
    host = host.split(":")[0]
    # {prefix}.myagentlab.homes
    if host.endswith(".myagentlab.homes"):
        sub = host[: -len(".myagentlab.homes")]
        if sub and "." not in sub:
            return sub
    # {prefix}.agent.myagentlab.homes（旧格式）
    if host.endswith(".agent.myagentlab.homes"):
        sub = host[: -len(".agent.myagentlab.homes")]
        if sub and "." not in sub:
            return sub
    return None


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request):
    host = request.headers.get("host", "")
    prefix = extract_prefix(host)
    if prefix is None:
        return JSONResponse({"detail": "unknown host: " + host}, status_code=404)

    port = find_port(prefix)
    if port is None:
        return JSONResponse({"detail": f"lease '{prefix}' not found or not running"}, status_code=404)

    url = f"http://127.0.0.1:{port}/" + path
    if request.url.query:
        url += "?" + request.url.query

    # 请求头：剔除 hop-by-hop 和 content-length（httpx 重新计算）
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "connection", "transfer-encoding", "accept-encoding")
    }
    body = await request.body()
    try:
        resp = await client.request(
            request.method, url, headers=headers, content=body or None,
        )
        # 响应头：剔除压缩/长度相关头（body 已被 httpx 解码为明文，重新让下游协商）
        out_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in DROP_RESPONSE_HEADERS
        }
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=out_headers,
        )
    except httpx.ConnectError:
        return JSONResponse({"detail": f"agent container on port {port} unreachable"}, status_code=502)
    except Exception as e:
        return JSONResponse({"detail": f"proxy error: {e}"}, status_code=502)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
