"""Exploración: correlaciones en niveles y en variaciones, y correlaciones con rezago."""

from __future__ import annotations

import numpy as np
import pandas as pd

from costos import EQUIPOS, MATERIAS_PRIMAS


def correlaciones(historico: pd.DataFrame, mensual: pd.DataFrame) -> pd.DataFrame:
    """Correlación de cada equipo con cada materia prima.

    Se calcula en frecuencia diaria y mensual, en niveles y en variaciones logarítmicas.
    Dos series con tendencia pueden correlacionar en niveles sin estar relacionadas;
    si la relación es real, también aparece en las variaciones.
    """
    columnas = MATERIAS_PRIMAS + EQUIPOS
    filas = []
    for frecuencia, tabla in (("diaria", historico[columnas]), ("mensual", mensual[columnas])):
        matrices = {
            "niveles": tabla.corr(),
            "variaciones": np.log(tabla).diff().dropna().corr(),
        }
        for tipo, matriz in matrices.items():
            for equipo in EQUIPOS:
                for materia in MATERIAS_PRIMAS:
                    filas.append(
                        {
                            "frecuencia": frecuencia,
                            "tipo": tipo,
                            "equipo": equipo,
                            "materia_prima": materia,
                            "correlacion": round(float(matriz.loc[equipo, materia]), 3),
                        }
                    )
    return pd.DataFrame(filas)


def correlaciones_por_rezago(mensual: pd.DataFrame, max_rezago: int = 3) -> pd.DataFrame:
    """Correlación entre la variación del equipo y la de la materia prima k meses antes.

    Promediar por mes crea algo de correlación en el rezago 1 por sí solo, así que un
    rezago solo cuenta si además mejora el error fuera de muestra.
    """
    variaciones = np.log(mensual).diff().dropna()
    filas = []
    for equipo in EQUIPOS:
        for materia in MATERIAS_PRIMAS:
            for rezago in range(max_rezago + 1):
                valor = variaciones[equipo].corr(variaciones[materia].shift(rezago))
                filas.append(
                    {
                        "equipo": equipo,
                        "materia_prima": materia,
                        "rezago_meses": rezago,
                        "correlacion": round(float(valor), 3),
                    }
                )
    return pd.DataFrame(filas)
