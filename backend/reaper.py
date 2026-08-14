"""Lease reaper: 定时扫描过期租约，停容器释放资源
运行：nohup python3 reaper.py &   （每分钟检查一次）
"""
import sys
import time
from datetime import datetime

sys.path.insert(0, ".AGENT_PLATFORM_ROOT/backend")

from database import get_db
from models import Lease
from docker_manager import stop_container


def reap_once():
    db = next(get_db())
    try:
        now = datetime.utcnow()
        expired = db.query(Lease).filter(Lease.status == "running", Lease.expires_at < now).all()
        for lease in expired:
            try:
                stop_container(lease.id)
                lease.status = "expired"
                db.commit()
                print(f"[reaper] {now} stopped expired lease {lease.id[:8]} ({lease.agent_id})")
            except Exception as e:
                print(f"[reaper] error on {lease.id[:8]}: {e}")
        return len(expired)
    finally:
        db.close()


if __name__ == "__main__":
    print("[reaper] started, checking every 60s")
    while True:
        try:
            n = reap_once()
            if n:
                print(f"[reaper] recycled {n} expired lease(s)")
        except Exception as e:
            print(f"[reaper] scan error: {e}")
        time.sleep(60)
