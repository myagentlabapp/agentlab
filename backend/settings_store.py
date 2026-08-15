"""Settings store: 品牌/定价/平台配置的读写（key-value 存 SQLite）"""

import json
from datetime import datetime

from database import get_db
from models import Setting
from app_secrets import get_env

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
    "footer_links": json.dumps([], ensure_ascii=False),
    # ---- 平台域名（部署期从 .env 读，运行期可在后台改） ----
    "platform_domain": get_env("PLATFORM_DOMAIN", ""),        # 域名主体，如 myagentlab.homes
    "platform_url": get_env("PLATFORM_URL", ""),              # 平台前端完整地址，如 https://agent.myagentlab.homes
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
    # ---- Cloudflare Turnstile ----
    "turnstile_enabled": "false",
    "turnstile_site_key": "",
    "turnstile_secret_key": "",
    # ---- login rate limit ----
    "login_rate_limit": "10",
    "login_lockout_threshold": "5",
    "login_lockout_minutes": "15",
    # ---- SMTP ----
    "email_register_enabled": "false",
    "smtp_host": "",
    "smtp_port": "465",
    "smtp_username": "",
    "smtp_password": "",
    "smtp_from_name": "",
    "smtp_use_ssl": "true",
    # ---- LLDAP ----
    "lldap_enabled": "false",
    "lldap_url": "",
    "lldap_bind_dn": "",
    "lldap_bind_password": "",
    "lldap_base_dn": "",
    "lldap_admin_group": "admins",
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
