# Pronóstico del costo de equipos a partir de materias primas

Solución de la prueba técnica "Gestión de costos operativos en un proyecto de construcción". Estima el costo de dos equipos a partir de los precios de tres materias primas (X, Y y Z), lo proyecta con intervalos mediante simulación de Montecarlo y expone los resultados con un **agente de IA (Gemini 3.1 Flash Lite)** detrás de **Apigee X** y un tablero en Streamlit, todo sobre Google Cloud.

> 📄 **Informe completo:** [`docs/INFORME.md`](docs/INFORME.md).

---

## Resultados clave

| Equipo | Materias primas que lo explican | R² | Error fuera de muestra (MAPE) | Pronóstico de septiembre de 2023 (p50) | Intervalo del 90 % (p5 a p95) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Equipo 1** | **X y Y** | 0.9997 | 0.34 % | 459.39 USD | 420.49 a 511.50 USD |
| **Equipo 2** | **X, Y y Z** | 0.9997 | 0.18 % | 923.24 USD | 860.97 a 992.94 USD |

* **Qué mueve cada equipo.** Y aporta el 96 % del costo del Equipo 1; Z es ruido para ese equipo. Z aporta el 77 % del costo del Equipo 2.
* **Selección fuera de muestra.** Se probaron todas las combinaciones de materias primas entrenando con 2010 a 2021 y midiendo el error en los 24 meses siguientes.
* **Incertidumbre.** 5,000 escenarios de Montecarlo dan la mediana (p50) y el intervalo del 90 % (p5 a p95) de cada mes.
* **Horizonte recomendado: 2 meses.** Con una tolerancia de 30 % en el ancho del intervalo, el Equipo 1 la rebasa al tercer mes y el Equipo 2 al quinto. Después conviene volver a pronosticar cada mes.

---

## Arquitectura

* **Pipeline mensual.** Un Cloud Run job, disparado por Cloud Scheduler el día 1 de cada mes, lee los CSV de Cloud Storage, valida los datos, elige el modelo, simula y publica en BigQuery.
* **Agente.** Un servicio privado de FastAPI en Cloud Run usa Gemini 3.1 Flash Lite con tres herramientas de solo lectura sobre BigQuery y registra el costo en USD de cada consulta.
* **Gateway.** Apigee X valida la llave de API, aplica cuota y límite de ráfagas, y llama al agente con un token de identidad de Google.
* **Tablero.** Una aplicación de Streamlit en Cloud Run muestra el pronóstico, un simulador de escenarios y el chat con el agente.

El diagrama y las decisiones de diseño están en el [anexo B del informe](docs/INFORME.md#anexo-b-arquitectura-propuesta-en-la-nube).

---

## Estructura del repositorio

```text
├── Datos/                  # CSV históricos de materias primas y equipos
├── Resultados/             # Tablas y gráficas que genera el pipeline
├── docs/
│   └── INFORME.md          # Informe de la prueba
├── notebooks/              # Exploración y experimentación
│   ├── 01_exploracion_y_modelos.ipynb
│   └── 02_pronostico_y_horizonte.ipynb
├── src/costos/
│   ├── datos.py            # Carga de datos y compuertas de calidad
│   ├── exploracion.py      # Correlaciones y rezagos
│   ├── modelo.py           # Selección fuera de muestra y regresión
│   ├── pronostico.py       # Backtesting, Montecarlo y horizonte
│   ├── graficas.py         # Gráficas del análisis
│   ├── salidas.py          # Escritura local, en Cloud Storage y en BigQuery
│   ├── pipeline.py         # Orquestador del proceso mensual
│   ├── agente/             # API, agente con Gemini y herramientas
│   └── dashboard/          # Tablero en Streamlit
├── tests/                  # 20 pruebas con pytest
├── docker/                 # Una imagen por componente
├── cloudbuild.yaml         # Construcción de imágenes con Cloud Build
├── Makefile                # Comandos de uso diario
└── pyproject.toml          # Dependencias y configuración
```

---

## Cómo ejecutar

### En local

Requiere [`uv`](https://docs.astral.sh/uv/) y `make`.

```bash
make setup      # Crea el entorno con Python 3.12 e instala las dependencias
make test       # Corre las 20 pruebas
make lint       # Revisa estilo y errores comunes
make pipeline   # Corre el análisis completo y regenera Resultados/
make notebooks  # Ejecuta los notebooks
```

El agente y el tablero también corren en local. Las rutas `/salud` y `/pronostico` no usan el modelo; `/preguntar` necesita credenciales de Google Cloud con acceso a Vertex AI.

```bash
make agente-local   # Agente en http://localhost:8080, lee Resultados/
curl "http://localhost:8080/pronostico?equipo=Equipo1&mes=2023-10"

uv pip install --python .venv/bin/python -e ".[dashboard]"
.venv/bin/python -m streamlit run src/costos/dashboard/app.py   # Sin acceso a BigQuery, lee Resultados/
```

### En la nube

* **Pronóstico directo por Apigee X:**
  ```bash
  curl -k -i "https://34.117.2.228.nip.io/v1/costos/pronostico?equipo=Equipo1&mes=2023-10&apikey=TU_API_KEY"
  ```

* **Pregunta en lenguaje natural al agente:**
  ```bash
  curl -k -i -X POST "https://34.117.2.228.nip.io/v1/costos/preguntar?apikey=TU_API_KEY" \
    -H "Content-Type: application/json" \
    -H "X-Consumidor: evaluador" \
    -d '{"pregunta": "¿Cuánto costará el Equipo1 en octubre de 2023 y qué materias primas lo mueven?"}'
  ```

* **Tablero web:** `https://dashboard-costos-1013958920551.us-central1.run.app`
