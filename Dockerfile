FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    LIFEAGENT_HOST=0.0.0.0 \
    LIFEAGENT_PORT=8777 \
    LIFEAGENT_DATA_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lifeagent ./lifeagent
VOLUME ["/data"]
EXPOSE 8777

CMD ["python", "-m", "lifeagent", "--kein-browser"]
