# Imagen del Dashboard interactivo en Streamlit
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[dashboard]" && useradd --create-home --uid 10001 app
USER app

EXPOSE 8080
CMD ["sh", "-c", "exec streamlit run src/costos/dashboard/app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false"]
