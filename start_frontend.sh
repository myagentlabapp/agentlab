#!/bin/bash
# 生产前端启动脚本（vite dev server，允许公网 host）
# 用法：bash /mnt/storage/agent-tenant-platform/start_frontend.sh
cd /mnt/storage/agent-tenant-platform/frontend
pkill -f '[v]ite --host' 2>/dev/null
sleep 2
VITE_ALLOWED_HOSTS='agent.myagentlab.homes,myagentlab.homes' setsid nohup npm run dev -- --host 0.0.0.0 --port 3000 > /home/yy/vite.log 2>&1 < /dev/null &
sleep 5
curl -s -o /dev/null -w 'vite: %{http_code}\n' http://localhost:3000/
