"""Lectura de los resultados que publica el pipeline.

- En GCP se leen de BigQuery (tablas `pronostico` y `modelo_final`).
- En local se leen de la carpeta Resultados/ que deja `make pipeline`.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

import pandas as pd


class Repositorio(Protocol):
    def pronostico(self, equipo: str, mes: str | None = None) -> list[dict]: ...

    def modelo(self, equipo: str) -> dict | None: ...


class RepositorioArchivos:
    """Lee pronostico.csv y modelo_final.json de una carpeta local."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self._pronostico: pd.DataFrame | None = None
        self._modelos: dict | None = None

    def _cargar(self) -> None:
        if self._pronostico is None:
            tabla = pd.read_csv(f"{self.base}/pronostico.csv", parse_dates=["fecha"])
            tabla["mes"] = tabla["fecha"].dt.strftime("%Y-%m")
            self._pronostico = tabla
            with open(f"{self.base}/modelo_final.json", encoding="utf-8") as archivo:
                self._modelos = json.load(archivo)

    def pronostico(self, equipo: str, mes: str | None = None) -> list[dict]:
        self._cargar()
        tabla = self._pronostico[self._pronostico["equipo"] == equipo]
        if mes:
            tabla = tabla[tabla["mes"] == mes]
        columnas = ["equipo", "mes", "h", "p5", "p50", "p95", "ancho_pct", "dentro_horizonte"]
        return json.loads(tabla[columnas].to_json(orient="records"))

    def modelo(self, equipo: str) -> dict | None:
        self._cargar()
        return self._modelos.get(equipo)


class RepositorioBigQuery:
    """Consulta las tablas que el pipeline publica en `proyecto.dataset`."""

    def __init__(self, dataset: str, cliente=None):
        from google.cloud import bigquery

        self._bq = bigquery
        self.dataset = dataset
        self.cliente = cliente or bigquery.Client(project=dataset.split(".")[0])

    def _consultar(self, sql: str, parametros: dict[str, str]) -> list[dict]:
        configuracion = self._bq.QueryJobConfig(
            query_parameters=[self._bq.ScalarQueryParameter(n, "STRING", v) for n, v in parametros.items()]
        )
        return [dict(fila.items()) for fila in self.cliente.query(sql, job_config=configuracion).result()]

    def pronostico(self, equipo: str, mes: str | None = None) -> list[dict]:
        sql = (
            "SELECT equipo, FORMAT_DATE('%Y-%m', fecha) AS mes, h, p5, p50, p95, ancho_pct, dentro_horizonte "
            f"FROM `{self.dataset}.pronostico` WHERE equipo = @equipo"
        )
        parametros = {"equipo": equipo}
        if mes:
            sql += " AND FORMAT_DATE('%Y-%m', fecha) = @mes"
            parametros["mes"] = mes
        return self._consultar(sql + " ORDER BY fecha", parametros)

    def modelo(self, equipo: str) -> dict | None:
        filas = self._consultar(
            f"SELECT * FROM `{self.dataset}.modelo_final` WHERE equipo = @equipo", {"equipo": equipo}
        )
        if not filas:
            return None
        fila = filas[0]
        return {
            "equipo": fila["equipo"],
            "variables": fila["variables"].split("+"),
            "coeficientes": json.loads(fila["coeficientes"]),
            "p_valores": json.loads(fila["p_valores"]),
            "r2": fila["r2"],
            "mape_prueba": fila["mape_prueba"],
            "p_cointegracion": fila["p_cointegracion"],
            "vif": json.loads(fila["vif"]),
            "ultimo_mes": fila["ultimo_mes"],
            "ultimos_precios": json.loads(fila["ultimos_precios"]),
        }


def crear_repositorio() -> Repositorio:
    """BigQuery si existe BQ_DATASET o bq-dataset; si no, la carpeta de RESULTADOS_URI."""
    dataset = os.getenv("BQ_DATASET") or os.getenv("bq-dataset", "")
    if dataset:
        return RepositorioBigQuery(dataset)
    return RepositorioArchivos(os.getenv("RESULTADOS_URI", "Resultados"))
