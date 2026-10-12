# Comandos de uso diario. Requiere uv: https://docs.astral.sh/uv/
PY := .venv/bin/python

.PHONY: setup pipeline test lint notebooks agente-local limpiar

setup:  ## Crea el entorno con Python 3.12 e instala el proyecto con todo lo necesario
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[pipeline,agente,dev]"

pipeline:  ## Corre el pipeline completo con los CSV locales y escribe en Resultados/
	$(PY) -m costos.pipeline --origen Datos --destino Resultados

test:  ## Pruebas unitarias y de punta a punta con datos sintéticos
	$(PY) -m pytest

lint:  ## Revisión de estilo y errores comunes
	$(PY) -m ruff check src tests

notebooks:  ## Ejecuta los notebooks y guarda sus salidas
	cd notebooks && ../$(PY) -m jupyter nbconvert --to notebook --execute --inplace *.ipynb

agente-local:  ## Levanta el agente en http://localhost:8080 leyendo Resultados/
	RESULTADOS_URI=Resultados $(PY) -m uvicorn costos.agente.app:app --port 8080 --reload

limpiar:  ## Borra cachés locales
	rm -rf .pytest_cache .ruff_cache src/*.egg-info
