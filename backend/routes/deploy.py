"""Container deployment routes."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from docker_manager import deploy_container
from models import Agent, Lease, User
from port_manager import allocate_port
from agent_domain import register_subdomain, unregister_subdomain, subdomain
from routes.admin import log_action
from routes.auth import get_current_user

router = APIRouter(prefix="/api/deploy", tags=["deploy"])


class DeployRequest(BaseModel):
    agent_id: str
    api_key: str
    duration_days: int


@router.post("")
def deploy(req: DeployRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Deploy a container for the requested agent and create a lease."""
    from settings_store import get_setting

    agent = db.query(Agent).filter(Agent.id == req.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 部署开关
    if get_setting("deploy_open", "true") != "true":
        raise HTTPException(status_code=403, detail="平台暂停部署")

    # 每用户实例上限
    max_inst = int(get_setting("max_instances_per_user", "3"))
    my_running = db.query(Lease).filter(Lease.user_id == user.id, Lease.status == "running").count()
    if my_running >= max_inst:
        raise HTTPException(status_code=400, detail=f"已达到实例上限（{max_inst} 个），请先停止部分实例")

    # 时长限制
    max_days = int(get_setting("max_duration_days", "30"))
    if req.duration_days > max_days:
        raise HTTPException(status_code=400, detail=f"单次部署最长 {max_days} 天")

    # 内存/CPU 配额（传给 docker_manager）
    mem_mb = int(get_setting("instance_mem_limit_mb", "2048"))
    cpu_quota = int(get_setting("instance_cpu_quota", "200000"))

    lease_id = str(uuid4())
    user_id = user.id

    try:
        port = allocate_port()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        container = deploy_container(
            agent_id=req.agent_id,
            user_id=user_id,
            api_key=req.api_key,
            port=port,
            lease_id=lease_id,
            mem_limit_mb=mem_mb,
            cpu_quota=cpu_quota,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Deploy failed: {exc}")

    container_id = getattr(container, "id", "") or ""
    now = datetime.utcnow()

    lease = Lease(
        id=lease_id,
        agent_id=req.agent_id,
        user_id=user_id,
        api_key=req.api_key,
        port=port,
        container_id=container_id,
        status="running",
        started_at=now,
        expires_at=now + timedelta(days=req.duration_days),
    )
    db.add(lease)
    db.commit()

    public_url = register_subdomain(lease_id)
    if public_url is None:
        from config import MACHINE_IP
        public_url = f"http://{MACHINE_IP}:{port}"

    log_action(db, user_id, "deploy", req.agent_id, "success")
    return {
        "lease_id": lease_id,
        "port": port,
        "url": public_url,
        "subdomain": subdomain(lease_id),
        "status": "running",
    }
