# Agent 租赁平台（智体工坊 · Agent Tenant Platform）

> myagentlab 第三条产品线：用户付费/免费租用 AI Agent（OpenClaw / Hermes / LobeChat），
> 每个实例 = 独立 Docker 容器 + 独立公网 HTTPS 子域名 + 用户自己的 API Key。

## 架构

```
公网用户 → https://agent.myagentlab.homes
  → CF Tunnel（116）→ 120:3000 前端（Vite）
  → Vite proxy /api → 120:8080 后端（FastAPI + SQLite）
租户实例 → https://{lease前8位}.myagentlab.homes
  → CF Tunnel → 120:80 proxy.py（动态反代）→ 容器端口
```

## 组件

| 目录 | 说明 |
|------|------|
| backend/ | FastAPI + SQLite：认证/部署/实例/管理/设置/日志 |
| frontend/ | React + Vite：门户/应用市场/我的实例/管理后台 |
| images/ | Agent 镜像（openclaw/hermes/lobechat） |
| proxy.py | 120:80 动态反代（按 Host 子域名路由到容器） |

## 后端

- **认证**：JWT（HS256，7 天），PBKDF2-SHA256 密码哈希
- **用户隔离**：/api/leases 只返回当前用户；admin 看全部
- **配置**：settings 表（28 项：品牌/定价/配额/平台开关），管理后台可改
- **过期回收**：reaper.py 每分钟扫描过期租约停容器（setsid nohup 常驻）
- **操作日志**：api_logs 表记录 deploy/stop
- **密钥**：app_secrets.py 从 .env 读取（JWT_SECRET / CF_TOKEN），.env 不进 git

## 前端

- 门户主页 → 应用市场 → 我的实例 → 管理后台（总览/用户/实例/容器/资源/平台设置）
- 平台设置 7 tab：品牌/定价/Agent/用户/平台规则/安全与备份/操作日志
- 品牌全动态：名称/Logo(图床链接)/主色调/公告/页脚 后台改全站生效

## 部署（120）

```bash
# 后端（setsid 防终端关闭）
cd backend && setsid nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8080 > /tmp/backend.log 2>&1 &

# 动态反代（80 端口需 root + httpx PYTHONPATH）
cd .AGENT_PLATFORM_ROOT && echo 'REDACTED' | sudo -S env PYTHONPATH=/home/yy/.local/lib/python3.10/site-packages setsid nohup python3 proxy.py > /tmp/proxy.log 2>&1 &

# 过期回收
cd backend && setsid nohup python3 reaper.py > /tmp/reaper.log 2>&1 &

# 前端（Vite dev server）
cd frontend && tmux new -d -s frontend 'npx vite --host 0.0.0.0 --port 3000'
```

## 管理员

- 账号：admin（初始密码 REDACTED，可在平台设置→安全与备份修改）
- 入口：登录后导航「⚙️ 管理后台」

## 注意

- 子域名注册需要 CF Token（backend/.env 的 CF_TOKEN）
- 首次部署前在平台设置确认：注册开关/部署开关/实例上限/时长
