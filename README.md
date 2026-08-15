# Agent 租赁平台（Agent Tenant Platform）

> 多租户 AI Agent 托管平台：用户付费/免费租用 AI Agent（OpenClaw / Hermes / LobeChat），
> 每个实例 = 独立 Docker 容器 + 独立公网 HTTPS 子域名 + 用户自己的 API Key。

## 架构

```
公网用户 → https://<platform_url>
  → CF Tunnel → <machine>:3000 前端（Vite）
  → Vite proxy /api → <machine>:8080 后端（FastAPI + SQLite）
租户实例 → https://{lease前8位}.<platform_domain>
  → CF Tunnel → <machine>:80 proxy.py（动态反代）→ 容器端口
```

`platform_domain`（域名主体）与 `platform_url`（前端地址）在管理后台「平台设置 → 品牌」配置，代码零硬编码。

## 组件

| 目录 | 说明 |
|------|------|
| backend/ | FastAPI + SQLite：认证/部署/实例/管理/设置/日志 |
| frontend/ | React + Vite：门户/应用市场/我的实例/管理后台 |
| images/ | Agent 镜像（openclaw/hermes/lobechat） |
| proxy.py | :80 动态反代（按 Host 子域名路由到容器） |

## 后端

- **认证**：JWT（HS256，7 天），PBKDF2-SHA256 密码哈希
- **用户隔离**：/api/leases 只返回当前用户；admin 看全部
- **配置**：settings 表（品牌/域名/定价/配额/安全开关），管理后台全可改
- **安全**：Cloudflare Turnstile / IP 限流 / 失败锁定 / 邮箱验证注册 / 忘记密码自助找回 / LLDAP 统一认证（全部后台开关，默认关）
- **过期回收**：reaper.py 每分钟扫描过期租约停容器
- **操作日志**：api_logs 表记录 deploy/stop
- **密钥**：app_secrets.py 从 backend/.env 读取，.env 不进 git

## 前端

- 门户主页 → 应用市场 → 我的实例 → 管理后台（总览/用户/实例/容器/资源/平台设置）
- 平台设置 tab：品牌/定价/Agent/用户/平台规则/安全与备份/操作日志
- 品牌全动态：名称/Logo/主色调/公告/页脚/域名 后台改全站生效

## 部署

### 1. 配置 backend/.env

```bash
# 必配
PLATFORM_DOMAIN=your-domain.com        # 域名主体（租户实例子域名后缀）
PLATFORM_URL=https://agent.your-domain.com   # 平台前端完整地址
MACHINE_IP=127.0.0.1

# Cloudflare Tunnel（实例子域名注册，不配则走内网直连）
CF_TOKEN=...
CF_ACCOUNT=...
CF_TUNNEL=...
CF_ZONE=...
TUNNEL_CNAME=<tunnel-id>.cfargotunnel.com
PROXY_TARGET=http://127.0.0.1:80

# 可选：模型 API 网关（注入容器）
OPENAI_BASE_URL=https://api.your-domain.com/v1
```

### 2. 启动

```bash
# 后端（setsid 防终端关闭）
cd backend && setsid nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 > /tmp/backend.log 2>&1 &

# 动态反代（80 端口需 root；httpx 装在用户目录时需 PYTHONPATH）
cd <项目目录> && sudo env PYTHONPATH=<python site-packages 路径> setsid nohup python3 proxy.py > /tmp/proxy.log 2>&1 &

# 过期回收
cd backend && setsid nohup python3 reaper.py > /tmp/reaper.log 2>&1 &

# 前端（Vite dev server；自定义域名时加 VITE_ALLOWED_HOSTS）
cd frontend && VITE_ALLOWED_HOSTS=.your-domain.com,localhost tmux new -d -s frontend 'npx vite --host 0.0.0.0 --port 3000'
```

### 3. 首次部署

1. 注册 admin 账号（第一个注册用户即管理员，或按部署说明初始化）
2. 管理后台「平台设置 → 品牌」确认：平台域名 / 前端地址 / 品牌
3. 按需开启：注册开关/部署开关/Turnstile/邮箱验证/LLDAP

## 管理员

- 账号：admin（初始密码在部署时设置，登录后可在 平台设置→安全与备份 修改）
- 入口：登录后导航「⚙️ 管理后台」

## 注意

- 子域名注册需要 Cloudflare Token（backend/.env 的 CF_TOKEN）；未配置时实例走内网直连（IP:端口）
- 所有域名/品牌/安全开关均可后台配置，仓库代码零硬编码域名
