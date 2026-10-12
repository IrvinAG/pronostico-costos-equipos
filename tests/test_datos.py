import pandas as pd
import pytest

from costos.datos import ErrorDeCalidad, a_mensual, leer_series, validar


def test_lee_los_cuatro_formatos(carpeta_datos):
    series, historico = leer_series(str(carpeta_datos))
    assert set(series) == {"X", "Y", "Z"}
    for serie in series.values():
        assert serie.index.is_monotonic_increasing
        assert serie.dtype == float
    assert list(historico.columns) == ["X", "Y", "Z", "Equipo1", "Equipo2"]
    # Y llega con decimales con coma: debe leerse igual que en el histórico
    assert (series["Y"] - historico["Y"]).abs().max() < 0.01


def test_validacion_pasa_con_datos_sanos(carpeta_datos):
    series, historico = leer_series(str(carpeta_datos))
    resumen = validar(series, historico)
    assert resumen["X"]["filas"] == len(series["X"])


def test_validacion_detecta_inconsistencias(carpeta_datos):
    series, historico = leer_series(str(carpeta_datos))
    roto = historico.copy()
    roto.iloc[10, roto.columns.get_loc("X")] += 5
    with pytest.raises(ErrorDeCalidad, match="no coincide"):
        validar(series, roto)


def test_validacion_detecta_precios_no_positivos(carpeta_datos):
    series, historico = leer_series(str(carpeta_datos))
    roto = historico.copy()
    roto.iloc[0, roto.columns.get_loc("Equipo1")] = -1
    with pytest.raises(ErrorDeCalidad, match="no positivos"):
        validar(series, roto)


def test_mensual_promedia_por_mes(carpeta_datos):
    _, historico = leer_series(str(carpeta_datos))
    mensual = a_mensual(historico)
    assert mensual.index[0] == pd.Timestamp("2010-01-01")
    assert (mensual.index.day == 1).all()
    assert len(mensual) == 164
