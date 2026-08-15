"""Email service: SMTP 验证码发送 + 校验（纯标准库实现）"""

import random
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate
from email.header import Header

from settings_store import get_setting

# ---- 验证码内存存储：{email|purpose: (code, expire_ts, sent_ts)} ----
_codes = {}
_lock = threading.Lock()

CODE_TTL = 600
RESEND_COOLDOWN = 60


def generate_code() -> str:
    return f"{random.randint(100000, 999999)}"


def send_code(email: str, purpose: str = "register") -> tuple:
    global _codes
    key = f"{email}|{purpose}"
    # ---- 1. 重发冷却检查 ----
    with _lock:
        rec = _codes.get(key)
        if rec:
            _, _, sent_ts = rec
            elapsed = time.time() - sent_ts
            if elapsed < RESEND_COOLDOWN:
                wait = int(RESEND_COOLDOWN - elapsed)
                return False, f"发送太频繁，请 {wait} 秒后再试"

    # ---- 2. 读取 SMTP 配置 ----
    host = get_setting("smtp_host", "")
    port = int(get_setting("smtp_port", "465") or "465")
    username = get_setting("smtp_username", "")
    password = get_setting("smtp_password", "")
    from_name = get_setting("smtp_from_name", "") or "Platform"
    use_ssl = get_setting("smtp_use_ssl", "true") == "true"

    if not host or not username or not password:
        return False, "SMTP 未配置，请联系管理员"

    # ---- 3. 生成验证码 ----
    code = generate_code()

    # ---- 4. 构造邮件 ----
    brand_name = get_setting("brand_name", "Platform")
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((str(Header(from_name, "utf-8")), username))
    msg["To"] = email

    if purpose == "reset":
        subject = f"[{brand_name}] 密码重置验证码"
        action_text = "重置密码"
    else:
        subject = f"[{brand_name}] 邮箱验证码"
        action_text = f"注册 {brand_name} 账号"

    msg["Subject"] = Header(subject, "utf-8")
    msg["Date"] = formatdate(localtime=True)
    from settings_store import get_setting
    _domain = (get_setting("platform_domain", "") or "").strip() or "localhost"
    msg["Message-ID"] = f"<{int(time.time())}@{_domain}>"

    html = (
        f'<div style="max-width:480px;margin:0 auto;font-family:sans-serif;padding:24px">'
        f'<h2 style="color:#4f46e5">{brand_name}</h2>'
        f'<p>您正在{action_text}，验证码为：</p>'
        f'<div style="font-size:32px;font-weight:bold;letter-spacing:8px;color:#4f46e5;'
        f'background:#f5f5f5;padding:16px 24px;border-radius:8px;text-align:center;margin:16px 0">{code}</div>'
        f'<p style="color:#666;font-size:14px">验证码 10 分钟内有效。如非本人操作请忽略此邮件。</p>'
        f'</div>'
    )
    text = f"[{brand_name}] 验证码: {code} (10分钟内有效)"
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # ---- 5. 发送 ----
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(username, password)
        server.sendmail(username, [email], msg.as_string())
        server.quit()
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP 认证失败（授权码错误？）"
    except smtplib.SMTPException as e:
        return False, f"邮件发送失败: {e}"
    except Exception as e:
        return False, f"发送异常: {e}"

    # ---- 6. 存验证码 ----
    with _lock:
        now = time.time()
        expired = {k: v for k, v in _codes.items() if v[1] > now}
        expired[key] = (code, now + CODE_TTL, now)
        _codes.clear()
        _codes.update(expired)

    return True, "验证码已发送"


def verify_code(email: str, code: str, purpose: str = "register") -> tuple:
    key = f"{email}|{purpose}"
    with _lock:
        rec = _codes.get(key)
        if not rec:
            return False, "请先发送验证码"
        stored_code, expire_ts, _ = rec
        if time.time() > expire_ts:
            _codes.pop(key, None)
            return False, "验证码已过期，请重新发送"
        if stored_code != code:
            return False, "验证码错误"
        _codes.pop(key, None)
    return True, "验证成功"
