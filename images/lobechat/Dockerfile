FROM lobehub/lobe-chat:latest

# 官方镜像自带正确启动（node server.js 监听 3210），不覆盖 CMD
# 租户 key 通过环境变量注入（部署时 docker_manager 传入）
ENV OPENAI_API_KEY=""
ENV OPENAI_PROXY_URL="https://api.example.com/v1"
ENV OPENAI_BASE_URL="https://api.example.com/v1"
ENV OPENAI_MODEL_LIST="-all,+glm-4.7,+glm-5.2,+deepseek-v4-flash,+deepseek-v4-pro,+doubao-seed-2.0-lite,+doubao-seed-2.0-mini,+kimi-k2.7-code,+kimi-k3,+minimax-m3"
ENV DEFAULT_AGENT_CONFIG="{\"model\":\"glm-4.7\",\"provider\":\"openai\"}"
ENV DEFAULT_AGENT_MODEL="glm-4.7"
