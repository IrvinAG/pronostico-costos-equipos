"""Pruebas del agente con un Gemini simulado: no hay llamadas reales ni costo."""

from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from costos.agente.agente import SIN_RESPUESTA, Agente
from costos.agente.app import app, obtener_agente, obtener_repositorio
from costos.agente.costos_llm import MODELO_POR_DEFECTO, costo_usd
from costos.agente.herramientas import crear_herramientas
from costos.agente.repositorio import RepositorioBigQuery


class RepositorioFalso:
    def pronostico(self, equipo, mes=None):
        filas = [
            {"equipo": equipo, "mes": "2023-09", "h": 1, "p5": 420.0, "p50": 460.0, "p95": 510.0},
            {"equipo": equipo, "mes": "2023-10", "h": 2, "p5": 405.0, "p50": 460.0, "p95": 538.0},
        ]
        return [f for f in filas if mes is None or f["mes"] == mes]

    def modelo(self, equipo):
        return {
            "equipo": equipo,
            "variables": ["X", "Y"],
            "coeficientes": {"const": 0.0, "X": 0.2, "Y": 0.8},
            "ultimos_precios": {"X": 85.0, "Y": 556.0},
            "ultimo_mes": "2023-08",
        }


def respuesta_llm(texto=None, pedidos=None, entrada=0, salida=0, razonamiento=0, cache=0):
    """Imita la respuesta del SDK: texto o llamadas a funciones, más el consumo de tokens."""
    return SimpleNamespace(
        text=texto,
        function_calls=pedidos,
        usage_metadata=SimpleNamespace(
            prompt_token_count=entrada,
            candidates_token_count=salida,
            thoughts_token_count=razonamiento,
            cached_content_token_count=cache,
        ),
    )


def pedido(nombre, **argumentos):
    return SimpleNamespace(name=nombre, args=argumentos)


class ChatFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.enviados = []

    def send_message(self, mensaje):
        self.enviados.append(mensaje)
        return self.respuestas.pop(0)


class ClienteFalso:
    def __init__(self, respuestas):
        self.chat = ChatFalso(respuestas)
        self.modelo = None
        self.config = None
        self.chats = SimpleNamespace(create=self._crear)

    def _crear(self, model, config):
        self.modelo, self.config = model, config
        return self.chat


def resultado_enviado(cliente, turno):
    """Lo que el agente le devolvió al modelo como resultado de una herramienta."""
    return cliente.chat.enviados[turno][0].function_response.response["result"]


def test_el_agente_usa_herramientas_y_suma_el_costo(capsys):
    cliente = ClienteFalso(
        [
            respuesta_llm(
                pedidos=[pedido("consultar_pronostico", equipo="Equipo 1", mes="2023-09")],
                entrada=800,
                salida=20,
                razonamiento=30,
            ),
            respuesta_llm(
                texto="En septiembre de 2023 el p50 es 460 USD, de 420 a 510.",
                entrada=950,
                salida=60,
                cache=500,
            ),
        ]
    )
    agente = Agente(RepositorioFalso(), cliente=cliente)
    resultado = agente.responder("¿Cuánto costará el Equipo1 en septiembre?", consumidor="evaluador")

    assert resultado["respuesta"].startswith("En septiembre de 2023")
    assert cliente.modelo == MODELO_POR_DEFECTO
    assert cliente.config.automatic_function_calling.disable is True
    assert resultado_enviado(cliente, 1)["filas"][0]["p50"] == 460.0

    uso = resultado["uso"]
    assert uso["llamadas"] == 2
    assert (uso["tokens_entrada"], uso["tokens_salida"], uso["tokens_lectura_cache"]) == (1750, 110, 500)
    esperado = costo_usd(MODELO_POR_DEFECTO, 800, 50) + costo_usd(MODELO_POR_DEFECTO, 950, 60, 500)
    assert abs(uso["costo_usd"] - round(esperado, 6)) < 1e-9

    logs = [json.loads(linea) for linea in capsys.readouterr().out.splitlines()]
    assert sum(1 for log in logs if log.get("evento") == "llm_uso") == 2
    assert logs[-1]["evento"] == "pregunta_respondida" and logs[-1]["consumidor"] == "evaluador"


def test_un_error_de_herramienta_vuelve_al_modelo():
    cliente = ClienteFalso(
        [
            respuesta_llm(pedidos=[pedido("borrar_datos"), pedido("consultar_modelo", equipos="Equipo1")]),
            respuesta_llm(texto="No tengo esa herramienta."),
        ]
    )
    resultado = Agente(RepositorioFalso(), cliente=cliente).responder("Borra todo")
    enviados = [parte.function_response.response["result"] for parte in cliente.chat.enviados[1]]
    assert "desconocida" in enviados[0]["error"]
    assert "Error ejecutando consultar_modelo" in enviados[1]["error"]
    assert resultado["respuesta"] == "No tengo esa herramienta."


def test_el_agente_corta_si_el_modelo_no_deja_de_pedir_herramientas():
    siempre_pide = [respuesta_llm(pedidos=[pedido("consultar_modelo", equipo="Equipo1")]) for _ in range(20)]
    resultado = Agente(RepositorioFalso(), cliente=ClienteFalso(siempre_pide)).responder("¿Qué lo mueve?")
    assert resultado["respuesta"] == SIN_RESPUESTA
    assert resultado["uso"]["llamadas"] == 9  # la pregunta más ocho rondas de herramientas


def test_el_costo_usa_la_tarifa_de_cada_tipo_de_token():
    # 1 M de entrada sin caché, 1 M leído de caché y 1 M de salida.
    assert costo_usd(MODELO_POR_DEFECTO, 2_000_000, 1_000_000, 1_000_000) == 0.25 + 0.025 + 1.50
    assert costo_usd("modelo-sin-precio", 1_000_000, 0) == costo_usd(MODELO_POR_DEFECTO, 1_000_000, 0)


def test_la_simulacion_de_escenarios_usa_los_coeficientes():
    herramientas = {h.__name__: h for h in crear_herramientas(RepositorioFalso())}
    salida = json.loads(herramientas["simular_escenario"]("Equipo1", "Y", 10))
    assert salida["impacto_usd_por_equipo"] == round(0.8 * 556.0 * 0.10, 2)
    nula = json.loads(herramientas["simular_escenario"]("Equipo1", "Z", 10))
    assert nula["impacto_usd_por_equipo"] == 0.0


def test_el_repositorio_de_bigquery_usa_consultas_con_parametros():
    class Fila(dict):
        pass

    class Consulta:
        def __init__(self, filas):
            self.filas = filas

        def result(self):
            return self.filas

    class ClienteFalsoBQ:
        def __init__(self):
            self.sql = []

        def query(self, sql, job_config):
            self.sql.append((sql, [p.name for p in job_config.query_parameters]))
            return Consulta([Fila(equipo="Equipo1", mes="2023-09", p50=460.0)])

    cliente = ClienteFalsoBQ()
    repo = RepositorioBigQuery("proyecto.costos", cliente=cliente)
    assert repo.pronostico("Equipo1", "2023-09")[0]["p50"] == 460.0
    sql, parametros = cliente.sql[0]
    assert "`proyecto.costos.pronostico`" in sql and parametros == ["equipo", "mes"]


def test_la_api_responde_sin_llm_y_con_llm():
    class AgenteFalso:
        def responder(self, pregunta, consumidor):
            return {"respuesta": f"ok: {pregunta}", "uso": {"costo_usd": 0.01}, "consumidor": consumidor}

    app.dependency_overrides[obtener_repositorio] = lambda: RepositorioFalso()
    app.dependency_overrides[obtener_agente] = lambda: AgenteFalso()
    try:
        cliente = TestClient(app)
        assert cliente.get("/salud").json()["estado"] == "ok"
        assert cliente.get("/pronostico", params={"equipo": "Equipo1"}).json()["filas"][0]["p50"] == 460.0
        assert cliente.get("/pronostico", params={"equipo": "Equipo9"}).status_code == 400
        assert cliente.get("/pronostico", params={"equipo": "Equipo1", "mes": "2030-01"}).status_code == 404
        respuesta = cliente.post(
            "/preguntar", json={"pregunta": "¿Y el Equipo2?"}, headers={"X-Consumidor": "eval"}
        )
        assert respuesta.json()["consumidor"] == "eval"
        assert cliente.post("/preguntar", json={"pregunta": "a"}).status_code == 422
    finally:
        app.dependency_overrides.clear()
