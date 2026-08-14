"""Agent catalog routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Agent

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def list_agents(db: Session = Depends(get_db)):
    """Return enabled agents in the catalog (下架的不显示)."""
    agents = db.query(Agent).filter(getattr(Agent, "enabled", 1) == 1).all()
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "icon": agent.icon,
            "image": agent.image,
            "price_monthly": agent.price_monthly,
        }
        for agent in agents
    ]
