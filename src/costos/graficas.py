"""Gráficas del análisis. Cada función devuelve una figura que `salidas.Destino` guarda."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

AZUL = "#1f6feb"
GRIS = "#555555"


def base100(mensual: pd.DataFrame):
    """Todas las series en base 100 para ver cuáles se mueven juntas."""
    figura, eje = plt.subplots(figsize=(11, 5))
    (mensual / mensual.iloc[0] * 100).plot(ax=eje, linewidth=1.4)
    eje.set_title("Precios mensuales en base 100 (enero 2010 = 100)")
    eje.set_xlabel("")
    eje.set_ylabel("Índice")
    eje.grid(alpha=0.3)
    figura.tight_layout()
    return figura


def pronostico(mensual: pd.DataFrame, tabla: pd.DataFrame, equipo: str, meses_historia: int = 36):
    """Histórico reciente, mediana pronosticada e intervalo del 90 % de un equipo."""
    datos = tabla[tabla["equipo"] == equipo]
    historia = mensual[equipo].iloc[-meses_historia:]
    figura, eje = plt.subplots(figsize=(11, 4.5))
    eje.plot(historia.index, historia.to_numpy(), color=GRIS, label="Histórico mensual")
    eje.plot(datos["fecha"], datos["p50"], color=AZUL, label="Pronóstico p50")
    eje.fill_between(
        datos["fecha"], datos["p5"], datos["p95"], color=AZUL, alpha=0.18, label="Intervalo del 90 %"
    )
    limite = datos.loc[datos["dentro_horizonte"], "fecha"].max()
    if pd.notna(limite):
        eje.axvline(limite, color="#999999", linestyle="--", linewidth=1)
        eje.text(
            limite, eje.get_ylim()[1], " fin del horizonte recomendado", va="top", fontsize=9, color="#666666"
        )
    eje.set_title(f"{equipo}: costo mensual en USD y pronóstico")
    eje.grid(alpha=0.3)
    eje.legend(loc="upper left")
    figura.tight_layout()
    return figura


def horizonte(backtest: pd.DataFrame, tabla: pd.DataFrame, ancho_maximo_pct: float):
    """Las dos curvas que justifican el horizonte: error por horizonte y ancho del intervalo."""
    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(12, 4.5))
    ingenuo = backtest[backtest["metodo"] == "ingenuo"]
    for materia, datos in ingenuo.groupby("materia_prima"):
        izquierda.plot(datos["h"], datos["mape"], marker="o", markersize=3, label=f"{materia}")
    izquierda.set_title("Error del pronóstico ingenuo de materias primas")
    izquierda.set_xlabel("Meses hacia adelante")
    izquierda.set_ylabel("MAPE (%)")
    izquierda.grid(alpha=0.3)
    izquierda.legend(title="Materia prima")

    for equipo, datos in tabla.groupby("equipo"):
        derecha.plot(datos["h"], datos["ancho_pct"], marker="o", markersize=3, label=str(equipo))
    derecha.axhline(
        ancho_maximo_pct, color="#cc3333", linestyle="--", linewidth=1, label="Ancho máximo tolerable"
    )
    derecha.set_title("Ancho del intervalo del 90 % del costo")
    derecha.set_xlabel("Meses hacia adelante")
    derecha.set_ylabel("Ancho como % del p50")
    derecha.grid(alpha=0.3)
    derecha.legend()
    figura.tight_layout()
    return figura
