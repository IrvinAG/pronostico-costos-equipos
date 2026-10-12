"""Backtesting de métodos, simulación de escenarios e intervalo por horizonte."""

from __future__ import annotations

import warnings
from collections.abc import Callable

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from costos.modelo import ModeloEquipo

Pronosticador = Callable[[pd.Series, int], np.ndarray]


def ingenuo(serie: pd.Series, horizonte: int) -> np.ndarray:
    """Repite el último valor observado. Es la referencia que todo modelo debe superar."""
    return np.repeat(float(serie.iloc[-1]), horizonte)


def arima(serie: pd.Series, horizonte: int) -> np.ndarray:
    """ARIMA(1,1,0) sobre el logaritmo del precio."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ajuste = ARIMA(np.log(serie.to_numpy(dtype=float)), order=(1, 1, 0)).fit()
    return np.exp(ajuste.forecast(horizonte))


def suavizamiento(serie: pd.Series, horizonte: int) -> np.ndarray:
    """Suavizamiento exponencial con tendencia amortiguada sobre el logaritmo del precio."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ajuste = ExponentialSmoothing(
            np.log(serie.to_numpy(dtype=float)), trend="add", damped_trend=True
        ).fit()
    return np.exp(ajuste.forecast(horizonte))


METODOS: dict[str, Pronosticador] = {"ingenuo": ingenuo, "arima": arima, "suavizamiento": suavizamiento}


def backtest(
    serie: pd.Series, pronosticar: Pronosticador, horizonte: int = 12, n_origenes: int = 36
) -> pd.Series:
    """Simula haber pronosticado desde `n_origenes` meses distintos y devuelve el MAPE por horizonte."""
    errores = []
    ultimo_origen = len(serie) - horizonte
    for origen in range(ultimo_origen - n_origenes + 1, ultimo_origen + 1):
        historia = serie.iloc[:origen]
        futuro = serie.iloc[origen : origen + horizonte].to_numpy(dtype=float)
        prediccion = pronosticar(historia, horizonte)
        for h in range(horizonte):
            errores.append((h + 1, abs(futuro[h] - prediccion[h]) / futuro[h] * 100))
    tabla = pd.DataFrame(errores, columns=["h", "ape"])
    return tabla.groupby("h")["ape"].mean()


def comparar_metodos(
    mensual: pd.DataFrame, materias: list[str], horizonte: int = 12, n_origenes: int = 36
) -> pd.DataFrame:
    """MAPE por horizonte de cada método para cada materia prima."""
    filas = []
    for materia in materias:
        for nombre, funcion in METODOS.items():
            curva = backtest(mensual[materia], funcion, horizonte, n_origenes)
            for h, valor in curva.items():
                filas.append(
                    {"materia_prima": materia, "metodo": nombre, "h": int(h), "mape": round(float(valor), 2)}
                )
    return pd.DataFrame(filas)


def simular(
    mensual: pd.DataFrame,
    modelo: ModeloEquipo,
    horizonte: int = 12,
    escenarios: int = 5000,
    semilla: int = 42,
) -> pd.DataFrame:
    """Pronóstico del equipo con intervalos por simulación de Montecarlo.

    1. Toma meses históricos completos al azar, lo que conserva la correlación entre materias primas.
    2. Encadena esos cambios desde el último precio observado para crear escenarios.
    3. Pasa cada escenario por la regresión del equipo y suma un residuo histórico al azar.
    4. Los percentiles 5 y 95 forman el intervalo del 90 %.
    """
    generador = np.random.default_rng(semilla)
    variables = modelo.variables
    rendimientos = np.log(mensual[variables]).diff().dropna().to_numpy()
    ultimo = mensual[variables].iloc[-1].to_numpy(dtype=float)

    meses = generador.integers(0, len(rendimientos), size=(escenarios, horizonte))
    caminos = ultimo * np.exp(np.cumsum(rendimientos[meses], axis=1))
    beta = np.array([modelo.coeficientes[v] for v in variables])
    ruido = generador.choice(modelo.residuos, size=(escenarios, horizonte))
    simulado = modelo.coeficientes["const"] + caminos @ beta + ruido

    fechas = pd.date_range(mensual.index[-1] + pd.offsets.MonthBegin(), periods=horizonte, freq="MS")
    p5, p50, p95 = np.percentile(simulado, [5, 50, 95], axis=0)
    return pd.DataFrame(
        {
            "equipo": modelo.equipo,
            "fecha": fechas,
            "h": np.arange(1, horizonte + 1),
            "p5": p5.round(2),
            "p50": p50.round(2),
            "p95": p95.round(2),
            "ancho_pct": ((p95 - p5) / p50 * 100).round(1),
        }
    )


def elegir_horizonte(pronostico: pd.DataFrame, ancho_maximo: float = 0.30) -> dict:
    """Horizonte recomendado: meses consecutivos en que el intervalo del 90 % sigue siendo útil.

    `ancho_maximo` es el ancho tolerable del intervalo como fracción del p50. Es un supuesto
    de negocio: 0.30 equivale a que el costo quede, con 90 % de probabilidad, dentro de
    un rango de unos ±15 % alrededor de la mediana.
    """
    limite = ancho_maximo * 100
    por_equipo = {}
    for equipo, tabla in pronostico.groupby("equipo"):
        cumple = (tabla.sort_values("h")["ancho_pct"] <= limite).astype(int)
        por_equipo[str(equipo)] = max(int(cumple.cummin().sum()), 1)
    return {
        "ancho_maximo_pct": round(limite, 1),
        "por_equipo": por_equipo,
        "recomendado_meses": min(por_equipo.values()),
    }
