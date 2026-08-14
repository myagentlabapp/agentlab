"""Lease stop routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from docker_manager import stop_container
from models import Lease, User
from routes.auth import get_current_user
from routes.admin import log_action

router = APIRouter(prefix="/api/stop", tags=["stop"])


@router.post("/{lease_id}")
def stop_lease(lease_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Stop the container for a lease and mark it stopped in the DB."""
    lease = db.query(Lease).filter(Lease.id == lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")
    if lease.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权操作该实例")

    stop_container(lease_id)
    lease.status = "stopped"
    db.commit()
    log_action(db, user.id, "stop", lease.agent_id, "success")

    return {"lease_id": lease_id, "status": "stopped"}
