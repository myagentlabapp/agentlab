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
    duration_days: int = 1
    billing_mode: str = "free"     # free / monthly / hourly / usage
    months: int = 1                # monthly 用
    hours: int = 1                 # hourly 用


def _check_balance(user: User, amount: float, db: Session):
    """余额充足校验"""
    bal = user.balance or 0
    if bal < amount:
        raise HTTPException(status_code=402, detail=f"余额不足：需要 ¥{amount:.2f}，当前 ¥{bal:.2f}，请先充值")


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

    # 计费模式与时长
    mode = req.billing_mode or "free"
    now = datetime.utcnow()

    if mode == "free":
        max_days = int(get_setting("max_duration_days", "30"))
        if req.duration_days > max_days:
            raise HTTPException(status_code=400, detail=f"单次部署最长 {max_days} 天")
        duration = timedelta(days=req.duration_days)
        cost = 0.0
    elif mode == "monthly":
        if req.months < 1 or req.months > 12:
            raise HTTPException(status_code=400, detail="月数范围 1-12")
        price = agent.price_monthly or 0
        if price <= 0:
            raise HTTPException(status_code=400, detail="该 Agent 不支持按月计费")
        cost = price * req.months
        duration = timedelta(days=req.months * 30)
    elif mode == "hourly":
        price_h = getattr(agent, "price_hourly", 0) or 0
        if price_h <= 0:
            raise HTTPException(status_code=400, detail="该 Agent 不支持按时计费")
        if req.hours < 1 or req.hours > 720:
            raise HTTPException(status_code=400, detail="时长范围 1-720 小时")
        cost = price_h * req.hours
        duration = timedelta(hours=req.hours)
    elif mode == "usage":
        # usage：按天从余额扣费（费率后台可配），预扣 3 天，到期续扣由 reaper 处理
        daily = float(get_setting("usage_daily_rate", "1") or 1)
        cost = daily * 3
        duration = timedelta(days=3)
    else:
        raise HTTPException(status_code=400, detail="不支持的计费模式")

    # 收费模式检查余额
    if mode in ("monthly", "hourly", "usage") and cost > 0:
        _check_balance(user, cost, db)

    # 内存/CPU 配额
    mem_mb = int(get_setting("instance_mem_limit_mb", "2048"))
    cpu_quota = int(get_setting("instance_cpu_quota", "200000"))

    lease_id = str(uuid4())
    user_id = user.id

    try:
        port = allocate_port()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        container, access_password = deploy_container(
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
    expires = now + duration

    lease = Lease(
        id=lease_id,
        agent_id=req.agent_id,
        user_id=user_id,
        api_key=req.api_key,
        port=port,
        container_id=container_id,
        status="running",
        started_at=now,
        expires_at=expires,
        access_password=access_password,
        billing_mode=mode,
    )
    db.add(lease)

    # 扣费
    if mode in ("monthly", "hourly", "usage") and cost > 0:
        user.balance = round((user.balance or 0) - cost, 2)
    db.commit()

    public_url = register_subdomain(lease_id)
    if public_url is None:
        from config import MACHINE_IP
        public_url = f"http://{MACHINE_IP}:{port}"

    log_action(db, user_id, "deploy", req.agent_id, "success")
    return {
        "lease_id": lease_id,
        "access_password": access_password,
        "port": port,
        "url": public_url,
        "subdomain": subdomain(lease_id),
        "status": "running",
        "billing_mode": mode,
        "cost": cost,
        "expires_at": expires.isoformat(),
        "balance": round(user.balance or 0, 2),
    }
