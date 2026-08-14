"""Settings store: 品牌/定价/平台配置的读写（key-value 存 SQLite）"""

import json
from datetime import datetime

from database import get_db
from models import Setting

DEFAULTS = {
    "brand_name": "智体工坊",
    "brand_logo": "🧪",
    "brand_tagline": "Agent 租赁平台",
    "brand_slogan_1": "租一个 AI Agent",
    "brand_slogan_2": "打开就能用",
    "brand_promo": "每个 Agent 都是独立容器 + 独立公网地址 + 你自己的 API Key。",
    "brand_free_text": "限时免费",
    "brand_free_sub": "限时免费，部署即用。",
    "brand_footer": "智体工坊 · Agent 租赁平台 · 2026",
    "brand_announcement": "",
    "brand_primary_color": "#4f46e5",
    "registration_open": "true",
    "deploy_open": "true",
    "max_duration_days": "30",
    "default_duration_days": "7",
    "free_mode": "true",
    "footer_links": json.dumps([
        {"label": "帮助文档", "url": "https://wiki.myagentlab.homes"},
        {"label": "API 网关", "url": "https://api.myagentlab.homes"},
    ], ensure_ascii=False),
    # ---- 扩展品牌 ----
    "brand_icp": "",                    # ICP 备案号
    "brand_stat_script": "",            # 统计代码（umami/GA）
    "brand_custom_css": "",             # 自定义 CSS
    # ---- 平台配额 ----
    "max_instances_per_user": "3",      # 每用户最大实例数
    "instance_mem_limit_mb": "2048",    # 每实例内存上限 MB
    "instance_cpu_quota": "200000",     # 每实例 CPU 配额
    "port_range_start": "9000",
    "port_range_end": "9100",
    # ---- 计费 ----
    "currency_symbol": "¥",             # 币种符号
    "billing_mode": "monthly",          # monthly|hourly|usage
    "discount_new_user": "100",         # 新用户折扣 %（100=无折扣）
}


def get_setting(key: str, default=None) -> str:
    db = next(get_db())
    try:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else (DEFAULTS.get(key, default) if default is None else default)
    finally:
        db.close()


def get_all_settings() -> dict:
    db = next(get_db())
    try:
        rows = db.query(Setting).all()
        db_values = {r.key: r.value for r in rows}
    finally:
        db.close()
    result = dict(DEFAULTS)
    result.update(db_values)
    return result


def set_settings(pairs: dict) -> None:
    db = next(get_db())
    try:
        for k, v in pairs.items():
            if k not in DEFAULTS:
                continue
            s = db.query(Setting).filter(Setting.key == k).first()
            if s:
                s.value = str(v)
            else:
                db.add(Setting(key=k, value=str(v)))
        db.commit()
    finally:
        db.close()


def init_defaults() -> None:
    db = next(get_db())
    try:
        for k, v in DEFAULTS.items():
            if not db.query(Setting).filter(Setting.key == k).first():
                db.add(Setting(key=k, value=str(v)))
        db.commit()
    finally:
        db.close()
