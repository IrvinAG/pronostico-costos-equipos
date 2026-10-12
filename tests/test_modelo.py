from costos.modelo import ajustar_final, comparar_combinaciones, elegir_variables


def test_la_seleccion_recupera_la_relacion_conocida(mensual):
    assert elegir_variables(comparar_combinaciones(mensual, "Equipo1")) == ["Z"]
    assert elegir_variables(comparar_combinaciones(mensual, "Equipo2")) == ["X", "Y"]


def test_el_modelo_final_tiene_diagnosticos_coherentes(mensual):
    modelo = ajustar_final(mensual, "Equipo2", ["X", "Y"], mape_prueba=1.0)
    assert modelo.r2 > 0.95
    assert modelo.p_valores["X"] < 0.05 and modelo.p_valores["Y"] < 0.05
    assert abs(modelo.coeficientes["X"] - 2.0) < 0.2
    assert modelo.p_cointegracion < 0.05
    assert set(modelo.a_dict()) >= {"variables", "coeficientes", "ultimos_precios"}
    assert "residuos" not in modelo.a_dict()
