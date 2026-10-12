import json

from costos.pipeline import main


def test_el_pipeline_corre_de_punta_a_punta(carpeta_datos, tmp_path):
    destino = tmp_path / "resultados"
    codigo = main(["--origen", str(carpeta_datos), "--destino", str(destino), "--escenarios", "300"])
    assert codigo == 0
    for archivo in [
        "pronostico.csv",
        "modelo_final.json",
        "seleccion_modelos.csv",
        "backtest_materias_primas.csv",
        "resumen.md",
        "horizonte.png",
    ]:
        assert (destino / archivo).exists(), archivo
    modelos = json.loads((destino / "modelo_final.json").read_text(encoding="utf-8"))
    assert modelos["Equipo1"]["variables"] == ["Z"]
    assert "Horizonte recomendado" in (destino / "resumen.md").read_text(encoding="utf-8")


def test_el_pipeline_falla_limpio_si_los_datos_estan_rotos(carpeta_datos, tmp_path):
    roto = tmp_path / "roto"
    roto.mkdir()
    for archivo in carpeta_datos.iterdir():
        (roto / archivo.name).write_bytes(archivo.read_bytes())
    historico = (roto / "historico_equipos.csv").read_text(encoding="utf-8").splitlines()
    partes = historico[1].split(",")
    partes[1] = str(float(partes[1]) + 10)
    historico[1] = ",".join(partes)
    (roto / "historico_equipos.csv").write_text("\n".join(historico) + "\n", encoding="utf-8")
    assert main(["--origen", str(roto), "--destino", str(tmp_path / "salida"), "--sin-graficas"]) == 2
