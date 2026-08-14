FROM node:22-slim
WORKDIR /app
COPY server.js .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
ENV OPENAI_API_KEY=""
ENV OPENAI_BASE_URL=""
ENV AGENT_PORT=8080
EXPOSE 8080
CMD ["./entrypoint.sh"]
