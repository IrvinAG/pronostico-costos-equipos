"""Pipeline de punta a punta: datos, modelo, pronóstico y publicación.

Uso local:
    python -m costos.pipeline --origen Datos --destino Resultados

Uso en GCP (lo hace el Cloud Run job):
    python -m costos.pipeline --origen gs://BUCKET/datos --destino gs://BUCKET/resultados \
        --bq-dataset PROYECTO.costos
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import pandas as pd

from costos import EQUIPOS, __version__
from costos.datos import ErrorDeCalidad, a_mensual, leer_series, validar
from costos.exploracion import correlaciones, correlaciones_por_rezago
from costos.modelo import ModeloEquipo, ajustar_final, comparar_combinaciones, elegir_variables
from costos.pronostico import comparar_metodos, elegir_horizonte, simular


def registrar(paso: str, severidad: str = "INFO", **datos) -> None:
    """Log estructurado en una línea JSON: Cloud Logging lo convierte en jsonPayload."""
    evento = {"severity": severidad, "componente": "pipeline", "paso": paso, **datos}
    print(json.dumps(evento, ensure_ascii=False, default=str), flush=True)


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pronóstico del costo de equipos")
    parser.add_argument(
        "--origen", default=os.getenv("ORIGEN_DATOS", "Datos"), help="Carpeta local o prefijo gs://"
    )
    parser.add_argument("--destino", default=os.getenv("DESTINO_RESULTADOS", "Resultados"))
    parser.add_argument(
        "--bq-dataset", default=os.getenv("BQ_DATASET", ""), help="proyecto.dataset; vacío = no publica"
    )
    parser.add_argument(
        "--corte", default="2021-08", help="Último mes de entrenamiento; lo posterior es prueba"
    )
    parser.add_argument("--horizonte", type=int, default=12, help="Meses a pronosticar")
    parser.add_argument(
        "--ancho-maximo",
        type=float,
        default=float(os.getenv("ANCHO_MAXIMO", "0.30")),
        help="Ancho tolerable del intervalo del 90 %% como fracción del p50",
    )
    parser.add_argument("--escenarios", type=int, default=5000, help="Escenarios de la simulación")
    parser.add_argument("--sin-graficas", action="store_true")
    return parser.parse_args(argv)


def tabla_markdown(tabla: pd.DataFrame) -> str:
    """Tabla en formato markdown sin dependencias extra."""
    encabezado = "| " + " | ".join(str(c) for c in tabla.columns) + " |"
    separador = "| " + " | ".join("---" for _ in tabla.columns) + " |"
    filas = ["| " + " | ".join(str(v) for v in fila) + " |" for fila in tabla.itertuples(index=False)]
    return "\n".join([encabezado, separador, *filas])


def tabla_modelo_bigquery(modelos: dict[str, ModeloEquipo]) -> pd.DataFrame:
    """El modelo final como tabla plana para BigQuery: los diccionarios viajan como JSON."""
    filas = []
    for modelo in modelos.values():
        datos = modelo.a_dict()
        filas.append(
            {
                "equipo": datos["equipo"],
                "variables": "+".join(datos["variables"]),
                "coeficientes": json.dumps(datos["coeficientes"]),
                "p_valores": json.dumps(datos["p_valores"]),
                "r2": datos["r2"],
                "mape_prueba": datos["mape_prueba"],
                "p_cointegracion": datos["p_cointegracion"],
                "vif": json.dumps(datos["vif"]),
                "ultimo_mes": datos["ultimo_mes"],
                "ultimos_precios": json.dumps(datos["ultimos_precios"]),
            }
        )
    return pd.DataFrame(filas)


def resumen(
    mensual: pd.DataFrame,
    modelos: dict[str, ModeloEquipo],
    seleccion: pd.DataFrame,
    backtest: pd.DataFrame,
    pronostico: pd.DataFrame,
    horizonte: dict,
) -> str:
    """Resumen legible de los resultados, regenerado en cada corrida."""
    modelos_md = pd.DataFrame(
        [
            {
                "Equipo": m.equipo,
                "Variables": ", ".join(m.variables),
                "Coeficientes": ", ".join(f"{v}: {m.coeficientes[v]:.3f}" for v in m.variables),
                "Constante": f"{m.coeficientes['const']:.2f}",
                "R²": f"{m.r2:.4f}",
                "MAPE de prueba": f"{m.mape_prueba:.2f} %",
                "p de cointegración": f"{m.p_cointegracion:.4f}",
                "VIF máximo": f"{max(m.vif.values()):.2f}",
            }
            for m in modelos.values()
        ]
    )
    errores = (
        backtest[backtest["h"].isin([1, 3, 6, 12])]
        .pivot_table(index=["materia_prima", "metodo"], columns="h", values="mape")
        .reset_index()
    )
    errores.columns = ["Materia prima", "Método"] + [f"MAPE h={c} (%)" for c in errores.columns[2:]]
    meses = horizonte["recomendado_meses"]
    tabla_pron = pronostico[pronostico["h"] <= max(meses, 3)].copy()
    tabla_pron["mes"] = pd.to_datetime(tabla_pron["fecha"]).dt.strftime("%Y-%m")
    tabla_pron = tabla_pron[["equipo", "mes", "p5", "p50", "p95", "ancho_pct", "dentro_horizonte"]]
    tabla_pron.columns = ["Equipo", "Mes", "p5", "p50", "p95", "Ancho (%)", "Dentro del horizonte"]

    partes = [
        "# Resumen de resultados",
        "",
        f"Generado por el pipeline v{__version__} con {len(mensual)} meses de datos, "
        f"de {mensual.index.min():%Y-%m} a {mensual.index.max():%Y-%m}.",
        "",
        "## Qué explica el costo de cada equipo",
        "",
        "Para cada equipo se probaron todas las combinaciones de materias primas, entrenando hasta el corte "
        "y midiendo el error en los meses posteriores. Se eligió la combinación más simple cuyo MAPE de prueba "
        "queda dentro del 10 % del mejor.",
        "",
        tabla_markdown(modelos_md),
        "",
        "### Todas las combinaciones probadas",
        "",
        tabla_markdown(seleccion[["equipo", "variables", "r2_entrenamiento", "mape_prueba", "elegida"]]),
        "",
        "## Pronóstico de materias primas: error por horizonte",
        "",
        tabla_markdown(errores),
        "",
        "## Pronóstico del costo de los equipos",
        "",
        f"Horizonte recomendado: **{meses} meses**. Es el tramo en que el intervalo del 90 % mide menos de "
        f"{horizonte['ancho_maximo_pct']:.0f} % del p50 para todos los equipos. Pasado ese punto, conviene "
        "re-pronosticar cada mes con datos nuevos.",
        "",
        tabla_markdown(tabla_pron),
        "",
    ]
    return "\n".join(partes)


def main(argv: list[str] | None = None) -> int:
    args = argumentos(argv)
    inicio = time.time()
    registrar("inicio", version=__version__, origen=args.origen, destino=args.destino)

    try:
        series, historico = leer_series(args.origen)
        calidad = validar(series, historico)
    except ErrorDeCalidad as error:
        registrar("validacion", severidad="ERROR", error=str(error))
        return 2
    registrar("validacion", resultado="ok", series=calidad)

    mensual = a_mensual(historico)
    registrar(
        "mensual",
        meses=len(mensual),
        desde=f"{mensual.index.min():%Y-%m}",
        hasta=f"{mensual.index.max():%Y-%m}",
    )

    tabla_corr = correlaciones(historico, mensual)
    tabla_rezagos = correlaciones_por_rezago(mensual)

    modelos: dict[str, ModeloEquipo] = {}
    selecciones = []
    for equipo in EQUIPOS:
        tabla = comparar_combinaciones(mensual, equipo, args.corte)
        variables = elegir_variables(tabla)
        etiqueta = "+".join(variables)
        mape_elegida = float(tabla.loc[tabla["variables"] == etiqueta, "mape_prueba"].iloc[0])
        modelos[equipo] = ajustar_final(mensual, equipo, variables, mape_elegida)
        tabla["elegida"] = tabla["variables"] == etiqueta
        selecciones.append(tabla)
        registrar("modelo", equipo=equipo, variables=variables, mape_prueba=mape_elegida)
    seleccion = pd.concat(selecciones, ignore_index=True)

    materias = sorted({v for modelo in modelos.values() for v in modelo.variables})
    backtest = comparar_metodos(mensual, materias, args.horizonte)
    registrar("backtest", materias=materias)

    pronostico = pd.concat(
        [simular(mensual, modelos[equipo], args.horizonte, args.escenarios) for equipo in EQUIPOS],
        ignore_index=True,
    )
    horizonte = elegir_horizonte(pronostico, args.ancho_maximo)
    pronostico["dentro_horizonte"] = pronostico["h"] <= horizonte["recomendado_meses"]
    registrar("pronostico", horizonte=horizonte)

    from costos.salidas import Destino, publicar_bigquery

    destino = Destino(args.destino)
    mensual_salida = mensual.reset_index().rename(columns={"Date": "fecha"})
    destino.csv(mensual_salida, "mensual.csv")
    destino.csv(tabla_corr, "correlaciones.csv")
    destino.csv(tabla_rezagos, "rezagos.csv")
    destino.csv(seleccion, "seleccion_modelos.csv")
    destino.csv(backtest, "backtest_materias_primas.csv")
    destino.csv(pronostico, "pronostico.csv")
    destino.json({equipo: modelo.a_dict() for equipo, modelo in modelos.items()}, "modelo_final.json")
    destino.json(horizonte, "horizonte.json")
    destino.texto(resumen(mensual, modelos, seleccion, backtest, pronostico, horizonte), "resumen.md")

    if not args.sin_graficas:
        from costos import graficas

        destino.figura(graficas.base100(mensual), "base100.png")
        destino.figura(
            graficas.horizonte(backtest, pronostico, horizonte["ancho_maximo_pct"]), "horizonte.png"
        )
        for equipo in EQUIPOS:
            destino.figura(
                graficas.pronostico(mensual, pronostico, equipo), f"pronostico_{equipo.lower()}.png"
            )
    registrar("salidas", destino=args.destino)

    if args.bq_dataset:
        para_bigquery = pronostico.copy()
        para_bigquery["fecha"] = para_bigquery["fecha"].dt.date
        mensual_bigquery = mensual_salida.copy()
        mensual_bigquery["fecha"] = mensual_bigquery["fecha"].dt.date
        publicadas = publicar_bigquery(
            {
                "pronostico": para_bigquery,
                "seleccion_modelos": seleccion,
                "backtest": backtest,
                "modelo_final": tabla_modelo_bigquery(modelos),
                "mensual": mensual_bigquery,
            },
            args.bq_dataset,
        )
        registrar("bigquery", tablas=publicadas)

    registrar("fin", segundos=round(time.time() - inicio, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
