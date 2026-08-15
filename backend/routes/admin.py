"""Admin routes: 平台管理后台 API（用户/实例/容器/资源）"""

from collections import defaultdict
from datetime import datetime

import docker
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Agent, Lease, User
from routes.auth import get_admin_user, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

client = docker.from_env()

@router.get("/overview")
def overview(db: Session = Depends(get_db), _admin: User = Depends(get_admin_user)):
    """平台总览：用户数、实例数、运行中、agent 分布"""
    leases = db.query(Lease).all()
    agents = db.query(Agent).all()

    users = defaultdict(lambda: {"count": 0, "running": 0})
    agent_dist = defaultdict(int)
    for l in leases:
        users[l.user_id]["count"] += 1
        if l.status == "running":
            users[l.user_id]["running"] += 1
        agent_dist[l.agent_id] += 1

    running_containers = 0
    try:
        running_containers = len(client.containers.list(filters={"label": "lease_id"}))
    except Exception:
        pass

    return {
        "total_users": len(users),
        "total_leases": len(leases),
        "running_leases": sum(1 for l in leases if l.status == "running"),
        "running_containers": running_containers,
        "agent_count": len(agents),
        "agent_distribution": dict(agent_dist),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/users")
def users(db: Session = Depends(get_db), _admin: User = Depends(get_admin_user)):
    """用户列表：每人部署数、运行中数、最近活动"""
    leases = db.query(Lease).all()
    by_user = defaultdict(list)
    for l in leases:
        by_user[l.user_id].append(l)

    result = []
    for uid, ls in sorted(by_user.items(), key=lambda x: -len(x[1])):
        running = sum(1 for l in ls if l.status == "running")
        last_active = max((l.started_at for l in ls), default=None)
        result.append({
            "user_id": uid,
            "deploy_count": len(ls),
            "running": running,
            "last_active": last_active.isoformat() if last_active else None,
        })
    return result


@router.get("/leases")
def all_leases(db: Session = Depends(get_db), _admin: User = Depends(get_admin_user)):
    """全部实例总览（含容器实时状态）"""
    leases = db.query(Lease).all()
    agents = {a.id: a for a in db.query(Agent).all()}
    from settings_store import get_setting
    _pd = (get_setting("platform_domain", "") or "").strip()
    result = []
    for l in leases:
        agent = agents.get(l.agent_id)
        result.append({
            "id": l.id,
            "agent_id": l.agent_id,
            "agent_name": agent.name if agent else l.agent_id,
            "user_id": l.user_id,
            "port": l.port,
            "status": l.status,
            "url": (f"https://{l.id[:8]}." + _pd) if (l.status == "running" and _pd) else None,
            "started_at": l.started_at.isoformat() if l.started_at else None,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
        })
    return result


@router.get("/containers")
def containers(_admin: User = Depends(get_admin_user)):
    """运行中容器实时状态（docker）"""
    try:
        cl = client.containers.list(all=True, filters={"label": "lease_id"})
        result = []
        for ct in cl:
            labels = ct.labels
            result.append({
                "name": ct.name,
                "status": ct.status,
                "lease_id": labels.get("lease_id", ""),
                "agent_id": labels.get("agent_id", ""),
                "user_id": labels.get("user_id", ""),
                "image": ct.image.tags[0] if ct.image.tags else "",
            })
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/resources")
def resources(_admin: User = Depends(get_admin_user)):
    """120 机器资源监控"""
    try:
        # 用 sed 取 free 的第二行（数据行），避免标题行解析错误
        stats = client.containers.run(
            "alpine:latest",
            "sh -c 'free -m | sed -n 2p; df -h / | tail -1; nproc'",
            remove=True, detach=False, stdout=True, stderr=False,
        ).decode()
        sep = chr(10)
        lines = [l for l in stats.strip().split(sep) if l.strip()]
        mem = lines[0].split()
        total_mem = int(mem[1]) if len(mem) > 1 and mem[1].isdigit() else 0
        used_mem = int(mem[2]) if len(mem) > 2 and mem[2].isdigit() else 0
        disk_line = lines[1].split() if len(lines) > 1 else []
        disk_used_pct = disk_line[4] if len(disk_line) > 4 else "?"
        return {
            "memory_mb": {"total": total_mem, "used": used_mem},
            "disk_root": disk_used_pct,
            "cpu_cores": lines[-1] if lines else "?",
            "running_agent_containers": len(client.containers.list(filters={"label": "lease_id"})),
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/settings")
def get_settings(_admin: User = Depends(get_admin_user)):
    """读取全部设置（含默认值）"""
    from settings_store import get_all_settings
    return get_all_settings()


class SettingsUpdate(BaseModel):
    settings: dict


@router.put("/settings")
def update_settings(req: SettingsUpdate, _admin: User = Depends(get_admin_user)):
    """批量保存设置（只接受白名单 key）"""
    from settings_store import set_settings
    set_settings(req.settings)
    return {"success": True}


@router.get("/agents")
def manage_agents(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Agent 管理列表（含 enabled 状态）"""
    agents = db.query(Agent).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "icon": a.icon,
            "image": a.image,
            "price_monthly": a.price_monthly,
            "enabled": getattr(a, "enabled", 1) != 0,
        }
        for a in agents
    ]


class AgentUpdate(BaseModel):
    name: str = None
    description: str = None
    icon: str = None
    image: str = None
    price_monthly: int = None
    enabled: bool = None


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, req: AgentUpdate, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """更新 Agent（名称/描述/图标/定价/上下架）"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if req.name is not None:
        agent.name = req.name
    if req.description is not None:
        agent.description = req.description
    if req.icon is not None:
        agent.icon = req.icon
    if req.image is not None:
        agent.image = req.image
    if req.price_monthly is not None:
        agent.price_monthly = req.price_monthly
    if req.enabled is not None:
        setattr(agent, "enabled", 1 if req.enabled else 0)
    db.commit()
    return {"success": True, "id": agent_id}


# ============ 扩展管理 API ============

@router.post("/agents")
def create_agent(req: AgentUpdate, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """新增 Agent"""
    if not req.name or not req.image:
        raise HTTPException(status_code=400, detail="名称和镜像必填")
    from uuid import uuid4
    agent_id = str(uuid4())[:8]
    agent = Agent(
        id=agent_id,
        name=req.name,
        description=req.description or "",
        icon=req.icon or "🤖",
        image=req.image,
        price_monthly=req.price_monthly or 0,
        enabled=1 if req.enabled is not False else 1,
    )
    db.add(agent)
    db.commit()
    return {"success": True, "id": agent_id}


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """删除 Agent（仅当无活跃租约）"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    active = db.query(Lease).filter(Lease.agent_id == agent_id, Lease.status == "running").first()
    if active:
        raise HTTPException(status_code=400, detail="该 Agent 有运行中实例，不能删除")
    db.delete(agent)
    db.commit()
    return {"success": True}


# ---- 用户管理 ----

@router.get("/user-manage")
def user_manage(_admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """用户管理列表（含状态）"""
    users = db.query(User).all()
    leases = db.query(Lease).all()
    by_user = {}
    for l in leases:
        by_user.setdefault(l.user_id, {"total": 0, "running": 0})
        by_user[l.user_id]["total"] += 1
        if l.status == "running":
            by_user[l.user_id]["running"] += 1
    return [
        {
            "id": u.id,
            "username": u.username,
            "is_admin": bool(u.is_admin),
            "enabled": getattr(u, "enabled", 1) != 0,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "instances": by_user.get(u.id, {"total": 0, "running": 0}),
        }
        for u in users
    ]


class UserManageReq(BaseModel):
    enabled: bool = None


@router.put("/user-manage/{user_id}")
def update_user(user_id: str, req: UserManageReq, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """禁用/启用用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="不能禁用管理员")
    if req.enabled is not None:
        setattr(user, "enabled", 1 if req.enabled else 0)
        db.commit()
    return {"success": True, "enabled": bool(user.enabled)}


class ResetPwdReq(BaseModel):
    new_password: str


@router.post("/user-manage/{user_id}/reset-password")
def reset_user_password(user_id: str, req: ResetPwdReq, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """重置用户密码"""
    from routes.auth import hash_password
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"success": True}


# ---- 安全 ----

class ChangePwdReq(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_admin_password(req: ChangePwdReq, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """修改自己密码（管理员或普通用户）"""
    from routes.auth import verify_password, hash_password
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"success": True}


# ---- 备份 ----

@router.get("/backup")
def backup_data(_admin: User = Depends(get_admin_user)):
    """导出数据备份（JSON）"""
    import json as _json
    db = next(get_db())
    try:
        agents = [{"id": a.id, "name": a.name, "description": a.description, "icon": a.icon,
                   "image": a.image, "price_monthly": a.price_monthly, "enabled": a.enabled}
                  for a in db.query(Agent).all()]
        users = [{"username": u.username, "is_admin": bool(u.is_admin)} for u in db.query(User).all()]
        leases = [{"id": l.id, "agent_id": l.agent_id, "user_id": l.user_id, "status": l.status,
                   "port": l.port, "started_at": l.started_at.isoformat() if l.started_at else None}
                  for l in db.query(Lease).all()]
        from settings_store import get_all_settings
        return {"agents": agents, "users": users, "leases": leases, "settings": get_all_settings()}
    finally:
        db.close()


# ---- 请求日志 ----

@router.get("/logs")
def api_logs(limit: int = 50, _admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """最近 API 请求日志"""
    from models import ApiLog
    logs = db.query(ApiLog).order_by(ApiLog.id.desc()).limit(limit).all()
    return [
        {
            "user_id": l.user_id,
            "action": l.action,
            "agent_id": l.agent_id,
            "status": l.status,
            "time": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


# ============ Logo 上传 ============

class LogoUploadReq(BaseModel):
    data: str  # base64 图片数据（不含 data: 前缀）


@router.post("/upload-logo")
def upload_logo(req: LogoUploadReq, _admin: User = Depends(get_admin_user)):
    """上传 logo 图片，返回可访问 URL"""
    import base64 as _b64
    import re as _re
    try:
        # 支持带 data:image/xxx;base64, 前缀
        if "," in req.data and req.data.startswith("data:"):
            m = _re.match(r"data:image/(\w+);base64,(.*)", req.data, _re.S)
            if not m:
                raise HTTPException(status_code=400, detail="图片格式不支持")
            ext = m.group(1)
            raw = m.group(2)
        else:
            raw = req.data
            ext = "png"
        img_bytes = _b64.b64decode(raw)
        if len(img_bytes) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片不能超过 2MB")
        # 校验魔数
        if ext == "png" and not img_bytes.startswith(b"\x89PNG"):
            raise HTTPException(status_code=400, detail="不是有效的 PNG 图片")
        if ext in ("jpg", "jpeg") and not img_bytes.startswith(b"\xff\xd8"):
            raise HTTPException(status_code=400, detail="不是有效的 JPEG 图片")
        fname = f"logo.{ext}"
        path = f"uploads/{fname}"
        with open(path, "wb") as f:
            f.write(img_bytes)
        return {"success": True, "url": f"/uploads/{fname}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")

# ===== 操作日志工具（deploy/stop 调用） =====
def log_action(db, user_id, action, agent_id, status="success"):
    """记录操作日志"""
    try:
        from models import ApiLog
        db.add(ApiLog(user_id=user_id, action=action, agent_id=agent_id, status=status))
        db.commit()
    except Exception:
        pass
