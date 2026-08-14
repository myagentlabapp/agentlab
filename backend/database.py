"""SQLAlchemy database setup, session management, and seeding."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DB_PATH
from models import Base, Agent, Lease

# SQLite engine
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Agent).count() == 0:
            agents = [
                Agent(
                    id="openclaw",
                    name="OpenClaw",
                    description="Open source AI assistant with multi-platform support",
                    icon="lobster",
                    image="myagentlab/openclaw:latest",
                    price_monthly=29,
                ),
                Agent(
                    id="hermes",
                    name="Hermes Agent",
                    description="NousResearch open-source agent framework with skills and memory",
                    icon="robot",
                    image="myagentlab/hermes:latest",
                    price_monthly=29,
                ),
                Agent(
                    id="lobechat",
                    name="LobeChat",
                    description="Open-source AI chat frontend with multi-model support",
                    icon="chat",
                    image="myagentlab/lobechat:latest",
                    price_monthly=19,
                ),
            ]
            db.add_all(agents)
            db.commit()
    finally:
        db.close()
