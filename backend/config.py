"""Configuration for the Agent Tenant Platform."""

from app_secrets import get_env

MACHINE_IP = get_env("MACHINE_IP", "127.0.0.1")
OPENAI_BASE_URL = get_env("OPENAI_BASE_URL", "https://api.example.com/v1")
API_BASE_URL = OPENAI_BASE_URL

DB_PATH = "data.db"

PORT_RANGE = (9000, 9100)
PORT_RANGE_START = 9000
PORT_RANGE_END = 9100

AGENTS = {
    "openclaw": {
        "id": "openclaw",
        "name": "OpenClaw",
        "description": "开源 AI 助手，支持多平台渠道、工具调用、定时任务",
        "icon": "lobster",
        "image": "myagentlab/openclaw:latest",
        "price_monthly": 0,
    },
    "hermes": {
        "id": "hermes",
        "name": "Hermes Agent",
        "description": "NousResearch 开源 Agent 框架，内置技能系统和持久记忆",
        "icon": "robot",
        "image": "myagentlab/hermes:latest",
        "price_monthly": 0,
    },
    "lobechat": {
        "id": "lobechat",
        "name": "LobeChat",
        "description": "开源 AI 聊天界面，支持多模型切换、多会话管理",
        "icon": "chat",
        "image": "myagentlab/lobechat:latest",
        "price_monthly": 0,
    },
}

SETTINGS = {
    "default_duration_days": 7,
    "max_duration_days": 30,
    "max_instances_per_user": 3,
}
