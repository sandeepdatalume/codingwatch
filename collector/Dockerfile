FROM python:3.11-slim

WORKDIR /app

COPY collector/requirements.txt .
COPY pyproject.toml .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

COPY collector/ ./collector/

ENV COLLECTOR_PORT=9876
ENV SQLITE_PATH=/data/metrics.db
ENV LOG_FILE=/data/metrics-collector.log

EXPOSE 9876

CMD ["python", "-m", "collector.app"]
