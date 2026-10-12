import pandas as pd

from costos.modelo import ajustar_final
from costos.pronostico import backtest, elegir_horizonte, ingenuo, simular


def test_backtest_devuelve_un_error_por_horizonte(mensual):
    curva = backtest(mensual["X"], ingenuo, horizonte=6, n_origenes=12)
    assert list(curva.index) == [1, 2, 3, 4, 5, 6]
    assert (curva > 0).all()


def test_la_simulacion_da_intervalos_ordenados(mensual):
    modelo = ajustar_final(mensual, "Equipo1", ["Z"], mape_prueba=1.0)
    tabla = simular(mensual, modelo, horizonte=6, escenarios=500)
    assert len(tabla) == 6
    assert (tabla["p5"] <= tabla["p50"]).all() and (tabla["p50"] <= tabla["p95"]).all()
    assert tabla["fecha"].iloc[0] == pd.Timestamp("2023-09-01")


def test_el_horizonte_corta_en_el_primer_mes_que_rebasa_el_ancho():
    tabla = pd.DataFrame(
        {
            "equipo": ["A"] * 4 + ["B"] * 4,
            "h": [1, 2, 3, 4] * 2,
            "ancho_pct": [10, 20, 35, 25, 10, 15, 20, 28],
        }
    )
    resultado = elegir_horizonte(tabla, ancho_maximo=0.30)
    assert resultado["por_equipo"] == {"A": 2, "B": 4}
    assert resultado["recomendado_meses"] == 2
