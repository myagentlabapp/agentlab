FROM python:3.11-slim
WORKDIR /app
COPY main.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
RUN pip install --no-cache-dir fastapi uvicorn
ENV OPENAI_API_KEY=""
ENV OPENAI_BASE_URL=""
ENV AGENT_PORT=8080
EXPOSE 8080
CMD ["./entrypoint.sh"]
