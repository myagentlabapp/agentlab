"""Lease reaper: 定时扫描过期租约，停容器释放资源
运行：nohup python3 reaper.py &   （间隔从 settings 读取，默认 60 秒）
"""
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from models import Lease
from docker_manager import stop_container


def _interval() -> int:
    """从 settings 读回收检查间隔（秒），默认 60"""
    try:
        from settings_store import get_setting
        return max(10, int(get_setting("reaper_interval", "60") or 60))
    except Exception:
        return 60


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


def _reap_usage():
    """usage 模式：到期前自动续扣（按天扣费），余额不足则回收"""
    try:
        from settings_store import get_setting
        db = next(get_db())
        try:
            daily = float(get_setting("usage_daily_rate", "1") or 1)
            now = datetime.utcnow()
            # 续扣窗口：usage 实例在到期前 6 小时内且余额够 -> 续 3 天
            from datetime import timedelta
            from models import User
            usage_leases = db.query(Lease).filter(
                Lease.status == "running",
                Lease.billing_mode == "usage",
            ).all()
            for lease in usage_leases:
                user = db.query(User).filter(User.id == lease.user_id).first()
                bal = (user.balance or 0) if user else 0
                remaining = (lease.expires_at - now).total_seconds() if lease.expires_at else 0
                if remaining <= 6 * 3600:  # 6 小时内到期
                    if bal >= daily * 3:
                        user.balance = round(bal - daily * 3, 2)
                        lease.expires_at = now + timedelta(days=3)
                        db.commit()
                        print(f"[reaper] usage续扣 lease {lease.id[:8]} +3天, 余额 {user.balance:.2f}")
                    else:
                        stop_container(lease.id)
                        lease.status = "expired"
                        db.commit()
                        print(f"[reaper] usage余额不足回收 lease {lease.id[:8]}")
        finally:
            db.close()
    except Exception as e:
        print(f"[reaper] usage scan error: {e}")


if __name__ == "__main__":
    print("[reaper] started")
    while True:
        try:
            n = reap_once()
            if n:
                print(f"[reaper] recycled {n} expired lease(s)")
            _reap_usage()
        except Exception as e:
            print(f"[reaper] scan error: {e}")
        time.sleep(_interval())
