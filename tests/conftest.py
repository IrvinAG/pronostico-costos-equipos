"""Datos sintéticos con los mismos formatos que los archivos reales y una relación conocida.

Equipo1 depende solo de Z; Equipo2 depende de X y Y. Si el método funciona, debe recuperarlo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="session")
def carpeta_datos(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("datos")
    generador = np.random.default_rng(7)
    fechas = pd.bdate_range("2010-01-04", "2023-08-31")

    def caminata(inicio: float, volatilidad: float) -> np.ndarray:
        return (inicio * np.exp(np.cumsum(generador.normal(0, volatilidad, len(fechas))))).round(2)

    x = caminata(80, 0.02)
    y = caminata(500, 0.012)
    z = caminata(2200, 0.012)
    equipo1 = (0.3 * z + generador.normal(0, 5, len(fechas))).round(2)
    equipo2 = (2.0 * x + 0.5 * y + generador.normal(0, 5, len(fechas))).round(2)

    # X.csv: separador coma, fechas ISO, orden descendente
    pd.DataFrame({"Date": fechas.strftime("%Y-%m-%d"), "Price": x}).iloc[::-1].to_csv(
        carpeta / "X.csv", index=False
    )
    # Y.csv: punto y coma, decimales con coma, fechas día/mes/año y BOM
    lineas = [
        f"{d.day}/{d.month}/{d.year};{str(v).replace('.', ',')}"
        for d, v in zip(fechas[::-1], y[::-1], strict=True)
    ]
    (carpeta / "Y.csv").write_text("﻿Date;Price\n" + "\n".join(lineas) + "\n", encoding="utf-8")
    # Z.csv: columnas invertidas
    pd.DataFrame({"Price": z, "Date": fechas.strftime("%Y-%m-%d")}).to_csv(carpeta / "Z.csv", index=False)
    # Histórico con todo junto
    pd.DataFrame(
        {
            "Date": fechas.strftime("%Y-%m-%d"),
            "Price_X": x,
            "Price_Y": y,
            "Price_Z": z,
            "Price_Equipo1": equipo1,
            "Price_Equipo2": equipo2,
        }
    ).to_csv(carpeta / "historico_equipos.csv", index=False)
    return carpeta


@pytest.fixture(scope="session")
def mensual(carpeta_datos):
    from costos.datos import a_mensual, leer_series

    _, historico = leer_series(str(carpeta_datos))
    return a_mensual(historico)
