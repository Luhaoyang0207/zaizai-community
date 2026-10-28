FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Non-root user; /app/data is a bind mount and must be writable by uid 1000.
RUN useradd --create-home --uid 1000 zaizai \
    && mkdir -p /app/config /app/data \
    && chown -R zaizai:zaizai /app
USER zaizai

CMD ["python", "-m", "zaizai"]
