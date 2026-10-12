"""Carga, validación y preparación de los precios.

Cada archivo de entrada trae un formato distinto. Este módulo lo documenta en código
y aplica compuertas de calidad que detienen el pipeline si los datos llegan rotos.
"""

from __future__ import annotations

import pandas as pd

from costos import EQUIPOS, MATERIAS_PRIMAS

ARCHIVOS = {
    "X": "X.csv",
    "Y": "Y.csv",
    "Z": "Z.csv",
    "historico": "historico_equipos.csv",
}


class ErrorDeCalidad(ValueError):
    """Los datos de entrada no pasan una compuerta de calidad."""


def ruta(origen: str, archivo: str) -> str:
    """Une una carpeta local o un prefijo gs:// con el nombre de un archivo."""
    return f"{origen.rstrip('/')}/{archivo}"


def leer_series(origen: str) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    """Lee los cuatro CSV respetando el formato de cada uno.

    - X.csv: separador coma, fechas ISO y orden descendente.
    - Y.csv: separador punto y coma, decimales con coma, fechas día/mes/año y BOM al inicio.
    - Z.csv: columnas invertidas, el precio va antes que la fecha.
    - historico_equipos.csv: materias primas y equipos en días hábiles.
    """
    x = pd.read_csv(ruta(origen, ARCHIVOS["X"]), parse_dates=["Date"])
    y = pd.read_csv(ruta(origen, ARCHIVOS["Y"]), sep=";", decimal=",", encoding="utf-8-sig")
    y["Date"] = pd.to_datetime(y["Date"], format="%d/%m/%Y")
    z = pd.read_csv(ruta(origen, ARCHIVOS["Z"]), parse_dates=["Date"])
    historico = pd.read_csv(ruta(origen, ARCHIVOS["historico"]), parse_dates=["Date"])

    series = {
        nombre: tabla.set_index("Date")["Price"].astype(float).sort_index()
        for nombre, tabla in (("X", x), ("Y", y), ("Z", z))
    }
    historico = historico.set_index("Date").sort_index()
    historico.columns = [columna.replace("Price_", "") for columna in historico.columns]
    return series, historico


def validar(series: dict[str, pd.Series], historico: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Aplica las compuertas de calidad y devuelve un resumen de cada serie.

    Revisa fechas duplicadas, faltantes, precios no positivos y que el histórico
    coincida con los archivos individuales en las fechas que comparten.
    """
    faltantes = [columna for columna in MATERIAS_PRIMAS + EQUIPOS if columna not in historico.columns]
    if faltantes:
        raise ErrorDeCalidad(f"Faltan columnas en el histórico: {faltantes}")

    revisar = dict(series)
    revisar.update({f"historico.{columna}": historico[columna] for columna in MATERIAS_PRIMAS + EQUIPOS})

    errores: list[str] = []
    for nombre, serie in revisar.items():
        if not serie.index.is_unique:
            errores.append(f"{nombre}: fechas duplicadas")
        if serie.isna().any():
            errores.append(f"{nombre}: {int(serie.isna().sum())} valores faltantes")
        if (serie <= 0).any():
            errores.append(f"{nombre}: precios no positivos")

    for materia in MATERIAS_PRIMAS:
        individual = series[materia]
        if not individual.index.is_unique or not historico.index.is_unique:
            continue
        comunes = historico.index.intersection(individual.index)
        if len(comunes) == 0:
            errores.append(f"{materia}: sin fechas en común con el histórico")
            continue
        diferencia = (historico.loc[comunes, materia] - individual.loc[comunes]).abs().max()
        if diferencia > 0.01:
            errores.append(
                f"{materia}: el histórico no coincide con {ARCHIVOS[materia]} (diferencia {diferencia:.4f})"
            )

    if errores:
        raise ErrorDeCalidad("; ".join(errores))

    return {
        nombre: {
            "filas": int(len(serie)),
            "desde": serie.index.min().date().isoformat(),
            "hasta": serie.index.max().date().isoformat(),
        }
        for nombre, serie in revisar.items()
    }


def a_mensual(historico: pd.DataFrame) -> pd.DataFrame:
    """Promedia cada serie por mes calendario. La fecha de cada mes queda en el día 1."""
    return historico[MATERIAS_PRIMAS + EQUIPOS].resample("MS").mean().dropna()
