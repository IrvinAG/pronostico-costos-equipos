# Imagen del pipeline mensual. La ejecuta un Cloud Run job, programado por Cloud Scheduler.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
# Solo las dependencias del pipeline, y un usuario sin privilegios para ejecutar.
RUN pip install ".[pipeline]" && useradd --create-home --uid 10001 app
USER app

# El origen, el destino y el dataset se configuran en el job: con los argumentos --origen,
# --destino y --bq-dataset, o con las variables ORIGEN_DATOS, DESTINO_RESULTADOS y BQ_DATASET.
ENTRYPOINT ["python", "-m", "costos.pipeline"]
