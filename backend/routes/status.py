"""Lease status and listing routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Lease, Agent, User
from routes.auth import get_current_user

router = APIRouter(prefix="/api", tags=["status"])


def _platform_domain() -> str:
    from settings_store import get_setting
    return (get_setting("platform_domain", "") or "").strip()


def _lease_to_dict(lease: Lease, agent: Agent = None):
    agent_name = agent.name if agent else lease.agent_id
    domain = _platform_domain()
    url = f"https://{lease.id[:8]}.{domain}" if (lease.status == "running" and domain) else None
    return {
        "id": lease.id,
        "agent_id": lease.agent_id,
        "agent_name": agent_name,
        "user_id": lease.user_id,
        "port": lease.port,
        "container_id": lease.container_id,
        "status": lease.status,
        "url": url,
        "access_password": getattr(lease, "access_password", ""),
        "started_at": lease.started_at.isoformat() if lease.started_at else None,
        "expires_at": lease.expires_at.isoformat() if lease.expires_at else None,
    }


@router.get("/status/{lease_id}")
def lease_status(lease_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return details for a single lease (owner only)."""
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    if lease.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权查看该实例")
    agent = db.query(Agent).filter(Agent.id == lease.agent_id).first()
    return _lease_to_dict(lease, agent)


@router.get("/leases")
def list_leases(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return current user's leases (admin sees all)."""
    query = db.query(Lease)
    if not user.is_admin:
        query = query.filter(Lease.user_id == user.id)
    leases = query.all()
    result = []
    for lease in leases:
        agent = db.query(Agent).filter(Agent.id == lease.agent_id).first()
        result.append(_lease_to_dict(lease, agent))
    return result
