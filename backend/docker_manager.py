"""docker_manager.py 增强:openclaw 真镜像配置挂载 + lobechat AUTH_SECRET + hermes config 生成

改动点:
1. AGENT_CONTAINER_PORT: openclaw 8080 -> 18789 (真 OpenClaw Gateway 端口)
2. deploy_container 按 agent 分支:
   - openclaw: 生成 openclaw.json (api_key 用部署请求参数, base_url 用 config.OPENAI_BASE_URL,
     模型用 config 可配, 默认 deepseek-v4-flash), 挂载到 /home/node/.openclaw/openclaw.json;
     env 注入 OPENCLAW_GATEWAY_TOKEN=access_password (租户访问 token)
   - lobechat: env 注入 AUTH_SECRET=secrets.token_hex(32) (Auth.js 必需) +
     DEFAULT_AGENT_CONFIG/OPENAI_MODEL_LIST (默认模型指向网关可用模型)
   - hermes: env 已注入 OPENAI_*, 由镜像入口 wrapper 生成 config.yaml (见镜像层)
3. 配置文件落盘目录: /mnt/storage/agent-tenant-platform/tenant-cfg/<lease8>/
"""

import json
import os
import secrets

import docker
from docker.errors import NotFound

from config import OPENAI_BASE_URL

client = docker.from_env()

# 各 agent 容器内监听端口 (真镜像端口)
AGENT_CONTAINER_PORT = {
    "openclaw": "18789",   # OpenClaw Gateway (Control UI / WS Gateway)
    "hermes": "8648",      # Hermes Studio Web UI
    "lobechat": "3210",    # LobeChat (Next.js)
}

# openclaw 默认模型 (平台网关可用的模型名, 后台可配覆盖)
DEFAULT_OPENCLAW_MODEL = "deepseek-v4-flash"

# openclaw 配置模板目录 (宿主机)
TENANT_CFG_DIR = "/mnt/storage/agent-tenant-platform/tenant-cfg"


def generate_access_password(length=12) -> str:
    """生成随机访问密码（字母+数字，无易混淆字符）"""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _build_openclaw_config(api_key: str, access_password: str, model: str = DEFAULT_OPENCLAW_MODEL) -> dict:
    """生成真 OpenClaw gateway 配置 (openclaw.json)。
    所有凭据来自部署请求参数/运行环境, 不硬编码。
    """
    return {
        "gateway": {"mode": "local", "port": 18789},
        "agents": {
            "defaults": {
                "workspace": "~/.openclaw/workspace",
                "model": {"primary": f"openai/{model}"},
            },
            "list": [
                {"id": "main", "identity": {"name": "Clawd", "theme": "helpful assistant", "emoji": "🦞"}}
            ],
        },
        "models": {
            "providers": {
                "openai": {
                    "baseUrl": OPENAI_BASE_URL.rstrip("/") + "/",
                    "apiKey": api_key,
                    "models": [{"id": model, "name": model}],
                }
            }
        },
    }


def _write_openclaw_cfg(lease_id: str, api_key: str, access_password: str) -> str:
    """把 openclaw.json 写到宿主目录, 返回挂载路径 (容器内路径)"""
    os.makedirs(TENANT_CFG_DIR, exist_ok=True)
    host_path = os.path.join(TENANT_CFG_DIR, lease_id[:8], "openclaw.json")
    os.makedirs(os.path.dirname(host_path), exist_ok=True)
    cfg = _build_openclaw_config(api_key, access_password)
    with open(host_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return "/home/node/.openclaw/openclaw.json"


def deploy_container(agent_id, user_id, api_key, port, lease_id, mem_limit_mb=2048, cpu_quota=200000):
    """Run a container for the given agent lease.

    Returns (container, access_password).
    """
    image = f"myagentlab/{agent_id}:latest"
    container_name = f"agent-{agent_id}-{lease_id[:8]}"
    labels = {
        "lease_id": lease_id,
        "agent_id": agent_id,
        "user_id": user_id,
    }
    cport = AGENT_CONTAINER_PORT.get(agent_id, "8080")
    access_password = generate_access_password()

    # ---- hermes 专用: 用预 chown 修复镜像, 绕过官方镜像的 root 守卫 ----
    # 官方 myagentlab/hermes:latest 是 root-owned 文件系统, hermes gateway 在
    # /opt/hermes 检出环境里拒绝以 root 启动
    # (见 hermes_cli/gateway.py _guard_official_docker_root_gateway), 否则 webui 的
    # gateway-runner 会循环崩溃 (code=1) → chat 消息无人处理 → 前端 timeout。
    # 解决: 改用预 chown 镜像 myagentlab/hermes:hermesfix2(内部 /home/agent 与
    # .hermes 已 chown 给 hermes 用户 uid=10000), 容器整体以 hermes 用户启动 →
    # 进程 geteuid()!=0, 守卫直接放行; 同时显式覆盖 entrypoint 为 node(否则会跑
    # hermesfix2 残留的 `sh -c 'chown...'` 入口, 容器起不来真正服务)。
    hermes_user = None
    if agent_id == "hermes":
        image = "myagentlab/hermes:hermesfix2"
        hermes_user = "hermes"

    # 每租户独立 bridge 网络(隔离租户间与宿主其它容器的横向访问)
    network_name = f"tenant-net-{lease_id[:8]}"
    try:
        network = client.networks.get(network_name)
    except docker.errors.NotFound:
        network = client.networks.create(network_name, driver="bridge")

    environment = {
        "OPENAI_API_KEY": api_key,
        "OPENAI_BASE_URL": OPENAI_BASE_URL,
        "OPENAI_PROXY_URL": OPENAI_BASE_URL,
        "AGENT_PORT": cport,
        # 第二道认证：实例自带访问密码
        "ACCESS_CODE": access_password,          # LobeChat: 聊天访问码
        "AUTH_PASSWORD": access_password,        # Hermes Studio: 登录密码
        "AUTH_USERNAME": "admin",
    }

    volumes = {}
    if agent_id == "openclaw":
        # 真 OpenClaw Gateway: 挂载 openclaw.json + 注入 gateway token
        cfg_container_path = _write_openclaw_cfg(lease_id, api_key, access_password)
        volumes[os.path.join(TENANT_CFG_DIR, lease_id[:8], "openclaw.json")] = {
            "bind": cfg_container_path,
            "mode": "rw",
        }
        environment["OPENCLAW_GATEWAY_TOKEN"] = access_password
    elif agent_id == "lobechat":
        # LobeChat: Auth.js 必需 AUTH_SECRET + 默认模型指向网关可用模型
        environment["AUTH_SECRET"] = secrets.token_hex(32)
        environment["DEFAULT_AGENT_CONFIG"] = json.dumps(
            {"model": DEFAULT_OPENCLAW_MODEL, "provider": "openai"}, ensure_ascii=False
        )
        environment["OPENAI_MODEL_LIST"] = f"-all,+{DEFAULT_OPENCLAW_MODEL}"

    # ---- hermes 容器以 hermes 用户运行 + 显式 entrypoint=node ----
    # hermesfix2 镜像入口残留为 `sh -c 'chown...'`, 必须覆盖成 node 才能启动真正服务
    # (实测: --user hermes --entrypoint node ... hermesfix2 dist/server/index.js)。
    # hermesfix2 已预 chown, 不再需要容器内 exec chown(cap_drop ALL 下也必然失败)。

    run_kwargs = dict(
        name=container_name,
        environment=environment,
        ports={f"{cport}/tcp": port},
        volumes=volumes,
        mem_limit=f"{mem_limit_mb}m",
        cpu_quota=cpu_quota,
        labels=labels,
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        # ---- 安全加固 2026-08-15 ----
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        pids_limit=512,
        network=network_name,
    )
    if hermes_user:
        # hermes 容器以非特权用户运行 + 显式覆盖 entrypoint 为 node
        # (hermesfix2 镜像残留入口是 `sh -c 'chown...'`, 不覆盖则容器起不来真正服务)
        run_kwargs["user"] = hermes_user
        run_kwargs["entrypoint"] = "node"
        run_kwargs["command"] = "dist/server/index.js"

    container = client.containers.run(image, **run_kwargs)

    return container, access_password


def stop_container(lease_id):
    """Stop and remove the container associated with a lease.

    Returns True if a container was found and stopped, False otherwise.
    """
    containers = client.containers.list(
        all=True, filters={"label": f"lease_id={lease_id}"}
    )
    if not containers:
        return False

    stopped = False
    for container in containers:
        try:
            container.stop(timeout=10)
        except Exception:
            pass
        try:
            container.remove()
            stopped = True
        except NotFound:
            stopped = True
        except Exception:
            pass
    # 回收租户网络
    try:
        network = client.networks.get(f"tenant-net-{lease_id[:8]}")
        network.remove()
    except Exception:
        pass
    return stopped


def get_container_status(lease_id):
    """Return the runtime status of a lease's container.

    Returns "running" or "stopped".
    """
    try:
        containers = client.containers.list(
            all=True, filters={"label": f"lease_id={lease_id}"}
        )
    except Exception:
        return "stopped"

    if not containers:
        return "stopped"

    for container in containers:
        try:
            if container.status == "running":
                return "running"
        except Exception:
            continue
    return "stopped"
