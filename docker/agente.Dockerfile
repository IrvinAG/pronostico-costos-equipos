# Imagen del agente. La sirve un Cloud Run service privado detrás de Apigee X.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[agente]" && useradd --create-home --uid 10001 app
USER app

EXPOSE 8080
# Cloud Run indica el puerto en la variable PORT.
CMD ["sh", "-c", "exec uvicorn costos.agente.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
