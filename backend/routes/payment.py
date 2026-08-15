"""虎皮椒支付路由：下单/回调/订单查询/余额充值"""

import hashlib
import time as time_mod
from datetime import datetime, timedelta
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Order, User, Agent, Lease
from routes.auth import get_current_user

router = APIRouter(prefix="/api/pay", tags=["pay"])

XUNHU_GATEWAY = "https://api.xunhupay.com/payment/do.html"


def _settings():
    from settings_store import get_setting
    return get_setting


def _sign(params: dict, secret: str) -> str:
    """虎皮椒签名：参数 ASCII 排序去 hash/空值，k=v&... + AppSecret，MD5 小写"""
    items = []
    for k in sorted(params.keys()):
        v = params[k]
        if k == "hash" or v is None or v == "":
            continue
        items.append(f"{k}={v}")
    raw = "&".join(items) + secret
    return hashlib.md5(raw.encode()).hexdigest()


def _create_xunhu_order(order_id: str, title: str, amount: float, notify_url: str, return_url: str):
    """调虎皮椒 API 下单，返回 (ok, url_qrcode/url 或错误)"""
    g = _settings()
    appid = g("xunhupay_appid", "")
    secret = g("xunhupay_appsecret", "")
    if not appid or not secret:
        return False, "虎皮椒未配置"
    params = {
        "version": "1.1",
        "appid": appid,
        "trade_order_id": order_id,
        "total_fee": f"{amount:.2f}",
        "title": title[:60],
        "time": str(int(time_mod.time())),
        "notify_url": notify_url,
        "return_url": return_url,
        "nonce_str": uuid4().hex[:16],
    }
    params["hash"] = _sign(params, secret)
    try:
        resp = requests.post(XUNHU_GATEWAY, data=params, timeout=15)
        data = resp.json()
        if data.get("errcode") == 0 or data.get("errcode") == "0" or data.get("url_qrcode"):
            return True, data.get("url_qrcode") or data.get("url", "")
        return False, data.get("errmsg", "虎皮椒下单失败")
    except Exception as e:
        return False, f"请求失败: {e}"


def _notify_base_url(request: Request) -> str:
    """构造 notify/return 地址（平台前端地址 + /#/pay/result）"""
    g = _settings()
    platform_url = g("platform_url", "").strip()
    if not platform_url:
        platform_url = f"http://{request.url.hostname}"
    return platform_url


class CreateOrderReq(BaseModel):
    agent_id: str
    billing_mode: str = "monthly"   # monthly / hourly
    months: int = 1                 # monthly 用
    hours: int = 1                  # hourly 用


class RechargeReq(BaseModel):
    amount: float = 10.0            # 充值金额（元，usage 余额）


@router.post("/create")
def create_order(req: CreateOrderReq, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """创建支付订单：monthly=月租, hourly=时租。usage 用 /recharge 充值余额"""
    g = _settings()
    if g("payment_enabled", "false") != "true":
        raise HTTPException(status_code=403, detail="支付功能未开启")
    agent = db.query(Agent).filter(Agent.id == req.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if req.billing_mode == "monthly":
        if req.months < 1 or req.months > 12:
            raise HTTPException(status_code=400, detail="月数范围 1-12")
        amount = agent.price_monthly * req.months
        title = f"租用 {agent.name} {req.months} 个月"
        duration_days = req.months * 30
        duration_hours = 0
    elif req.billing_mode == "hourly":
        if not getattr(agent, "price_hourly", 0):
            raise HTTPException(status_code=400, detail="该 Agent 不支持按时计费")
        if req.hours < 1 or req.hours > 24 * 30:
            raise HTTPException(status_code=400, detail="时长范围 1-720 小时")
        amount = agent.price_hourly * req.hours
        title = f"租用 {agent.name} {req.hours} 小时"
        duration_days = 0
        duration_hours = req.hours
    else:
        raise HTTPException(status_code=400, detail="不支持的计费模式")

    order_id = uuid4().hex
    order = Order(
        id=order_id, user_id=user.id, agent_id=req.agent_id,
        title=title, amount=amount, billing_mode=req.billing_mode,
        duration_days=duration_days, duration_hours=duration_hours, status="pending",
    )
    db.add(order)
    db.commit()

    platform_url = _notify_base_url(request)
    notify_url = f"{platform_url}/api/pay/notify"
    return_url = f"{platform_url}/#/pay/result?order_id={order_id}"
    ok, pay_url = _create_xunhu_order(order_id, title, amount, notify_url, return_url)
    if not ok:
        order.status = "canceled"
        db.commit()
        raise HTTPException(status_code=502, detail=pay_url)
    return {"order_id": order_id, "amount": amount, "pay_url": pay_url}


@router.post("/recharge")
def recharge(req: RechargeReq, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """充值余额（usage 模式预充值）"""
    g = _settings()
    if g("payment_enabled", "false") != "true":
        raise HTTPException(status_code=403, detail="支付功能未开启")
    if req.amount < 1 or req.amount > 5000:
        raise HTTPException(status_code=400, detail="充值金额 1-5000 元")
    order_id = uuid4().hex
    order = Order(
        id=order_id, user_id=user.id, agent_id="", title=f"余额充值 {req.amount:.2f} 元",
        amount=req.amount, billing_mode="usage", status="pending",
    )
    db.add(order)
    db.commit()

    platform_url = _notify_base_url(request)
    notify_url = f"{platform_url}/api/pay/notify"
    return_url = f"{platform_url}/#/pay/result?order_id={order_id}"
    ok, pay_url = _create_xunhu_order(order_id, order.title, req.amount, notify_url, return_url)
    if not ok:
        order.status = "canceled"
        db.commit()
        raise HTTPException(status_code=502, detail=pay_url)
    return {"order_id": order_id, "amount": req.amount, "pay_url": pay_url}


@router.post("/notify")
async def notify(request: Request, db: Session = Depends(get_db)):
    """虎皮椒支付回调（公网可访问），验签后更新订单状态"""
    form = await request.form()
    params = {k: v for k, v in form.items()}
    secret = _settings()("xunhupay_appsecret", "")
    calc = _sign(params, secret)
    if calc != params.get("hash", ""):
        return {"errcode": 1, "errmsg": "签名错误"}
    if params.get("status") != "OD":
        return {"errcode": 1, "errmsg": "未支付"}
    order_id = params.get("trade_order_id", "")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return {"errcode": 1, "errmsg": "订单不存在"}
    if order.status == "paid":
        return {"errcode": 0, "errcode_msg": "已处理"}  # 幂等
    order.status = "paid"
    order.paid_at = datetime.utcnow()
    db.commit()

    # 按计费模式处理
    if order.billing_mode == "usage":
        user = db.query(User).filter(User.id == order.user_id).first()
        if user:
            user.balance = round((user.balance or 0) + order.amount, 2)
            db.commit()
    return {"errcode": 0, "errcode_msg": "success"}


@router.get("/orders")
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """当前用户订单列表"""
    orders = db.query(Order).filter(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(50).all()
    return [
        {
            "id": o.id, "title": o.title, "amount": o.amount,
            "billing_mode": o.billing_mode, "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in orders
    ]


@router.get("/balance")
def my_balance(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """当前用户余额"""
    return {"balance": round(user.balance or 0, 2)}
