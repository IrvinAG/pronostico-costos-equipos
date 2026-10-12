"""Selección de variables fuera de muestra y modelo final de cada equipo."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import coint

from costos import MATERIAS_PRIMAS


def mape(real, prediccion) -> float:
    """Error porcentual absoluto medio."""
    real = np.asarray(real, dtype=float)
    prediccion = np.asarray(prediccion, dtype=float)
    return float(np.mean(np.abs(real - prediccion) / real) * 100)


def separar(mensual: pd.DataFrame, corte: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corte por fecha: entrena hasta `corte` y prueba con lo posterior. Nunca al azar."""
    entrenamiento = mensual.loc[:corte]
    prueba = mensual.loc[mensual.index > entrenamiento.index.max()]
    return entrenamiento, prueba


def comparar_combinaciones(mensual: pd.DataFrame, equipo: str, corte: str = "2021-08") -> pd.DataFrame:
    """Ajusta una regresión con cada combinación de materias primas y mide su error en prueba."""
    entrenamiento, prueba = separar(mensual, corte)
    filas = []
    for cantidad in range(1, len(MATERIAS_PRIMAS) + 1):
        for combinacion in combinations(MATERIAS_PRIMAS, cantidad):
            variables = list(combinacion)
            ajuste = sm.OLS(entrenamiento[equipo], sm.add_constant(entrenamiento[variables])).fit()
            prediccion = ajuste.predict(sm.add_constant(prueba[variables], has_constant="add"))
            filas.append(
                {
                    "equipo": equipo,
                    "variables": "+".join(variables),
                    "n_variables": cantidad,
                    "r2_entrenamiento": round(float(ajuste.rsquared), 4),
                    "mape_prueba": round(mape(prueba[equipo], prediccion), 3),
                }
            )
    return pd.DataFrame(filas).sort_values(["mape_prueba", "n_variables"]).reset_index(drop=True)


def elegir_variables(tabla: pd.DataFrame, tolerancia: float = 0.10) -> list[str]:
    """Elige la combinación más simple cuyo error de prueba quede cerca del mejor.

    Una combinación es candidata si su MAPE no supera al mejor en más de `tolerancia`
    relativa. Entre las candidatas gana la de menos variables; si empatan, la de menor MAPE.
    """
    mejor = tabla["mape_prueba"].min()
    candidatas = tabla[tabla["mape_prueba"] <= mejor * (1 + tolerancia)]
    elegida = candidatas.sort_values(["n_variables", "mape_prueba"]).iloc[0]
    return str(elegida["variables"]).split("+")


@dataclass
class ModeloEquipo:
    """Modelo final de un equipo, ajustado con todos los datos."""

    equipo: str
    variables: list[str]
    coeficientes: dict[str, float]
    p_valores: dict[str, float]
    r2: float
    mape_prueba: float
    p_cointegracion: float
    vif: dict[str, float]
    ultimo_mes: str
    ultimos_precios: dict[str, float]
    residuos: np.ndarray = field(repr=False)

    def a_dict(self) -> dict:
        """Versión serializable, sin los residuos."""
        return {
            "equipo": self.equipo,
            "variables": self.variables,
            "coeficientes": {k: round(v, 6) for k, v in self.coeficientes.items()},
            "p_valores": {k: round(v, 6) for k, v in self.p_valores.items()},
            "r2": round(self.r2, 6),
            "mape_prueba": self.mape_prueba,
            "p_cointegracion": round(self.p_cointegracion, 6),
            "vif": self.vif,
            "ultimo_mes": self.ultimo_mes,
            "ultimos_precios": {k: round(v, 4) for k, v in self.ultimos_precios.items()},
        }


def ajustar_final(
    mensual: pd.DataFrame, equipo: str, variables: list[str], mape_prueba: float
) -> ModeloEquipo:
    """Ajusta el modelo elegido con todos los datos y calcula sus diagnósticos.

    - Errores estándar HAC: corrigen la confianza de los coeficientes cuando los residuos
      se parecen mes a mes, algo casi seguro en series de tiempo.
    - Cointegración de Engle-Granger: p < 0.05 indica una relación de largo plazo real.
    - VIF: menor a 5 indica que las variables no se pisan entre sí.
    """
    exogenas = sm.add_constant(mensual[variables])
    ajuste = sm.OLS(mensual[equipo], exogenas).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    p_coint = float(coint(mensual[equipo], mensual[variables], return_results=False)[1])
    if len(variables) > 1:
        vif = {
            columna: round(float(variance_inflation_factor(exogenas.to_numpy(), i)), 3)
            for i, columna in enumerate(exogenas.columns)
            if columna != "const"
        }
    else:
        vif = {variables[0]: 1.0}
    ultimo = mensual.iloc[-1]
    return ModeloEquipo(
        equipo=equipo,
        variables=variables,
        coeficientes={k: float(v) for k, v in ajuste.params.items()},
        p_valores={k: float(v) for k, v in ajuste.pvalues.items()},
        r2=float(ajuste.rsquared),
        mape_prueba=float(mape_prueba),
        p_cointegracion=p_coint,
        vif=vif,
        ultimo_mes=mensual.index[-1].strftime("%Y-%m"),
        ultimos_precios={materia: float(ultimo[materia]) for materia in variables},
        residuos=np.asarray(ajuste.resid, dtype=float),
    )
