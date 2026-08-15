"""Public settings: 前端品牌读取（无需登录）"""

from fastapi import APIRouter
from settings_store import get_all_settings
from models import Agent
from database import get_db

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def public_settings():
    """前端品牌/平台配置（公开，不含敏感项）"""
    s = get_all_settings()
    return {
        "brand_name": s.get("brand_name", "智体工坊"),
        "brand_logo": s.get("brand_logo", "🧪"),
        "brand_tagline": s.get("brand_tagline", "Agent 租赁平台"),
        "brand_slogan_1": s.get("brand_slogan_1", "租一个 AI Agent"),
        "brand_slogan_2": s.get("brand_slogan_2", "打开就能用"),
        "brand_promo": s.get("brand_promo", ""),
        "brand_free_text": s.get("brand_free_text", "限时免费"),
        "brand_free_sub": s.get("brand_free_sub", "限时免费，部署即用。"),
        "brand_footer": s.get("brand_footer", ""),
        "brand_announcement": s.get("brand_announcement", ""),
        "brand_primary_color": s.get("brand_primary_color", "#4f46e5"),
        "registration_open": s.get("registration_open", "true") == "true",
        "deploy_open": s.get("deploy_open", "true") == "true",
        "max_duration_days": int(s.get("max_duration_days", "30")),
        "default_duration_days": int(s.get("default_duration_days", "7")),
        "free_mode": s.get("free_mode", "true") == "true",
        # ---- Turnstile（公开字段，仅 site_key + 开关，不发 secret） ----
        "turnstile_enabled": s.get("turnstile_enabled", "false") == "true",
        "turnstile_site_key": s.get("turnstile_site_key", ""),
        "email_register_enabled": s.get("email_register_enabled", "false") == "true",
        "lldap_enabled": s.get("lldap_enabled", "false") == "true",
        "platform_domain": s.get("platform_domain", "").strip(),
        "platform_url": s.get("platform_url", "").strip(),
    }
