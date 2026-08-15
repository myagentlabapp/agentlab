"""Docker container lifecycle management for agent leases.

v2：部署时注入随机访问密码（ACCESS_CODE / AUTH_PASSWORD），作为第二道认证防线。
"""

import secrets

import docker
from docker.errors import NotFound

from config import OPENAI_BASE_URL

client = docker.from_env()

# 各 agent 容器内监听端口（lobechat 官方镜像 3210，其余自研镜像 8080）
AGENT_CONTAINER_PORT = {
    "openclaw": "8080",
    "hermes": "8648",
    "lobechat": "3210",
}


def generate_access_password(length=12) -> str:
    """生成随机访问密码（字母+数字，无易混淆字符）"""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


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

    container = client.containers.run(
        image,
        name=container_name,
        environment=environment,
        ports={f"{cport}/tcp": port},
        mem_limit=f"{mem_limit_mb}m",
        cpu_quota=cpu_quota,
        labels=labels,
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        # ---- 安全加固 2026-08-15 ----
        # 最小权限:去掉全部 Linux capabilities + 禁止提权 + 限进程数防 fork bomb
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        pids_limit=512,
        # 每租户独立 bridge 网络:租户间互不可达,与宿主其它容器隔离
        network=network_name,
    )
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
