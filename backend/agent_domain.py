"""Agent 实例公网子域名注册/注销（Cloudflare API）
每个 lease 分配 {lease_id[:8]}.{platform_domain} 一级子域
（一级子域被 *.{platform_domain} Universal 证书免费覆盖，无需等证书）
域名主体从 settings 读取（platform_domain），未配置则跳过 CF 注册走内网直连。
"""
import json
import ssl
import urllib.request
import urllib.error

from app_secrets import CF_TOKEN, get_env
CF_ACCOUNT = get_env("CF_ACCOUNT", "")
CF_TUNNEL = get_env("CF_TUNNEL", "")
CF_ZONE = get_env("CF_ZONE", "")
TUNNEL_CNAME = get_env("TUNNEL_CNAME", "")
PROXY_TARGET = get_env("PROXY_TARGET", "http://127.0.0.1:80")

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _platform_domain() -> str:
    """读取配置的域名主体（后台可改）"""
    from settings_store import get_setting
    return (get_setting("platform_domain", "") or "").strip()


def _api(base, method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Authorization": "Bearer " + CF_TOKEN, "Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, context=_ctx, timeout=20)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"success": False, "errors": [{"message": e.read().decode()[:200]}]}


def _tunnel(method, path, body=None):
    return _api(f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/cfd_tunnel/{CF_TUNNEL}/", method, path, body)


def _zone(method, path, body=None):
    return _api(f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE}/", method, path, body)


def subdomain(lease_id: str) -> str:
    """生成租户子域名；未配置域名返回空串（走内网直连）"""
    domain = _platform_domain()
    if not domain:
        return ""
    return f"{lease_id[:8]}.{domain}"


def register_subdomain(lease_id: str) -> str | None:
    """注册子域名（DNS CNAME + tunnel ingress），返回完整 https 地址；失败返回 None"""
    sub = subdomain(lease_id)
    if not sub:
        return None  # 未配置域名 → deploy.py 走内网直连 fallback
    # 1. DNS CNAME（幂等：已存在则跳过）
    dns = _zone("GET", f"dns_records?name={sub}&type=CNAME")
    exists = any(r["name"] == sub for r in dns.get("result", []))
    if not exists:
        r = _zone("POST", "dns_records", {
            "type": "CNAME", "name": sub, "content": TUNNEL_CNAME, "proxied": True,
        })
        if not r.get("success"):
            print(f"[agent-domain] DNS add failed for {sub}: {r.get('errors')}")
            return None

    # 2. tunnel ingress 规则（幂等）
    cur = _tunnel("GET", "configurations")
    if not cur.get("success"):
        return None
    ingress = cur["result"]["config"]["ingress"]
    if not any(r.get("hostname") == sub for r in ingress):
        ingress.insert(-1, {"hostname": sub, "service": PROXY_TARGET})
        r = _tunnel("PUT", "configurations", {"config": {"ingress": ingress}})
        if not r.get("success"):
            print(f"[agent-domain] ingress add failed for {sub}: {r.get('errors')}")
            return None
    return f"https://{sub}"


def unregister_subdomain(lease_id: str) -> None:
    """注销子域名（部署失败/停止时清理）"""
    sub = subdomain(lease_id)
    if not sub:
        return
    # 1. 删 DNS
    dns = _zone("GET", f"dns_records?name={sub}")
    for rec in dns.get("result", []):
        if rec["name"] == sub:
            _zone("DELETE", f"dns_records/{rec['id']}")
    # 2. 删 ingress
    cur = _tunnel("GET", "configurations")
    if cur.get("success"):
        ingress = cur["result"]["config"]["ingress"]
        new_ingress = [r for r in ingress if r.get("hostname") != sub]
        if len(new_ingress) != len(ingress):
            _tunnel("PUT", "configurations", {"config": {"ingress": new_ingress}})
