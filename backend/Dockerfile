FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN python -m venv /opt/venv \
    && pip install --no-cache-dir --require-hashes -r requirements.lock

COPY alembic.ini ./alembic.ini
COPY logging.json ./logging.json
COPY migrations ./migrations
COPY app ./app

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logging.json"]
