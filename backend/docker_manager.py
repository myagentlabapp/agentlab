"""Docker container lifecycle management for agent leases."""

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


def deploy_container(agent_id, user_id, api_key, port, lease_id, mem_limit_mb=2048, cpu_quota=200000):
    """Run a container for the given agent lease.

    Returns the started container object.
    """
    image = f"myagentlab/{agent_id}:latest"
    container_name = f"agent-{agent_id}-{lease_id[:8]}"
    labels = {
        "lease_id": lease_id,
        "agent_id": agent_id,
        "user_id": user_id,
    }
    cport = AGENT_CONTAINER_PORT.get(agent_id, "8080")
    environment = {
        "OPENAI_API_KEY": api_key,
        "OPENAI_BASE_URL": OPENAI_BASE_URL,
        "OPENAI_PROXY_URL": OPENAI_BASE_URL,
        "AGENT_PORT": cport,
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
    )
    return container


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
