"""Escritura de resultados en una carpeta local o en Cloud Storage, y publicación en BigQuery."""

from __future__ import annotations

import io
import json
import os

import fsspec
import matplotlib.pyplot as plt
import pandas as pd


class Destino:
    """Escribe archivos en una carpeta local o bajo un prefijo gs://, con la misma interfaz."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        if "://" not in self.base:
            os.makedirs(self.base, exist_ok=True)

    def ruta(self, nombre: str) -> str:
        return f"{self.base}/{nombre}"

    def csv(self, tabla: pd.DataFrame, nombre: str) -> str:
        with fsspec.open(self.ruta(nombre), "w", encoding="utf-8") as archivo:
            tabla.to_csv(archivo, index=False)
        return self.ruta(nombre)

    def json(self, objeto, nombre: str) -> str:
        with fsspec.open(self.ruta(nombre), "w", encoding="utf-8") as archivo:
            json.dump(objeto, archivo, ensure_ascii=False, indent=2, default=str)
        return self.ruta(nombre)

    def texto(self, contenido: str, nombre: str) -> str:
        with fsspec.open(self.ruta(nombre), "w", encoding="utf-8") as archivo:
            archivo.write(contenido)
        return self.ruta(nombre)

    def figura(self, figura, nombre: str) -> str:
        buffer = io.BytesIO()
        figura.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
        plt.close(figura)
        with fsspec.open(self.ruta(nombre), "wb") as archivo:
            archivo.write(buffer.getvalue())
        return self.ruta(nombre)


def publicar_bigquery(tablas: dict[str, pd.DataFrame], dataset: str, cliente=None) -> list[str]:
    """Carga cada tabla en `proyecto.dataset`, reemplazando su contenido anterior."""
    from google.cloud import bigquery

    cliente = cliente or bigquery.Client(project=dataset.split(".")[0])
    configuracion = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    publicadas = []
    for nombre, tabla in tablas.items():
        destino = f"{dataset}.{nombre}"
        cliente.load_table_from_dataframe(tabla, destino, job_config=configuracion).result()
        publicadas.append(destino)
    return publicadas
