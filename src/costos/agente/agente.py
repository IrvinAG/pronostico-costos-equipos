"""Agente que responde preguntas sobre costos con Gemini y herramientas.

Diferencia con la IA convencional: el modelo de regresión predice; el agente decide qué
herramienta usar, observa el resultado y repite hasta poder responder con cifras.
"""

from __future__ import annotations

import json
import os

from costos.agente.costos_llm import MODELO_POR_DEFECTO, UsoAcumulado, registrar
from costos.agente.herramientas import crear_herramientas
from costos.agente.repositorio import Repositorio

SISTEMA = """Eres el analista de costos de un proyecto de construcción. Respondes en español, en frases claras y ejecutivas.

Reglas:
- Toda cifra de costos, pronósticos o modelos sale obligatoriamente de una de tus herramientas:
  * consultar_pronostico: para montos del costo en USD (p50 mediana, intervalo del 90% p5 a p95) y horizonte recomendado.
  * consultar_modelo: para conocer qué materias primas (X, Y o Z) explican el costo de cada equipo y sus coeficientes.
  * simular_escenario: para evaluar impactos ante cambios en materias primas.
- Si el usuario pregunta por contexto de mercado, macroeconómico o tendencias del sector, complementa el análisis con tu propio conocimiento económico general del mercado de materias primas e industria de la construcción.
"""

ITERACIONES_MAXIMAS = 8
SIN_RESPUESTA = "No pude generar una respuesta. Reformula la pregunta sobre costos, pronóstico o materias primas."


class Agente:
    def __init__(self, repo: Repositorio, cliente=None, modelo: str | None = None):
        self.repo = repo
        self.modelo = modelo or os.getenv("LLM_MODELO") or os.getenv("llm-modelo") or MODELO_POR_DEFECTO
        self.cliente = cliente or self._crear_cliente()

    def _crear_cliente(self):
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("gemini-api-key")
        if api_key:
            return genai.Client(api_key=api_key)
        # Gemini en Vertex AI: se autentica con la cuenta de servicio del Cloud Run; no hay llave que guardar.
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.getenv("google-cloud-project") or "prueba-prod-511304"
        region = os.getenv("LLM_REGION") or os.getenv("llm-region") or "us-central1"
        return genai.Client(vertexai=True, project=project, location=region)

    def responder(self, pregunta: str, consumidor: str = "anonimo") -> dict:
        from google.genai import types

        herramientas = {fn.__name__: fn for fn in crear_herramientas(self.repo)}
        config = types.GenerateContentConfig(
            system_instruction=SISTEMA,
            tools=list(herramientas.values()),
            temperature=0.2,
            # El ciclo de herramientas corre aquí y no dentro del SDK, para medir cada llamada al modelo.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        chat = self.cliente.chats.create(model=self.modelo, config=config)
        uso = UsoAcumulado(modelo=self.modelo)

        respuesta = chat.send_message(pregunta)
        self._medir(uso, respuesta, consumidor)
        for _ in range(ITERACIONES_MAXIMAS):
            pedidos = respuesta.function_calls
            if not pedidos:
                break
            resultados = [
                types.Part.from_function_response(
                    name=pedido.name, response={"result": self._ejecutar(herramientas, pedido)}
                )
                for pedido in pedidos
            ]
            respuesta = chat.send_message(resultados)
            self._medir(uso, respuesta, consumidor)

        # Si el modelo agotó las iteraciones pidiendo herramientas, no hay texto que entregar.
        texto = "" if respuesta.function_calls else (respuesta.text or "").strip()
        resumen = uso.a_dict()
        registrar({"evento": "pregunta_respondida", "consumidor": consumidor, **resumen})
        return {"respuesta": texto or SIN_RESPUESTA, "uso": resumen}

    def _medir(self, uso: UsoAcumulado, respuesta, consumidor: str) -> None:
        detalle = uso.agregar(respuesta.usage_metadata)
        registrar({"evento": "llm_uso", "consumidor": consumidor, "modelo": self.modelo, **detalle})

    @staticmethod
    def _ejecutar(herramientas: dict, pedido) -> dict:
        funcion = herramientas.get(pedido.name)
        if funcion is None:
            return {"error": f"Herramienta desconocida: {pedido.name}"}
        try:
            return json.loads(funcion(**dict(pedido.args or {})))
        except Exception as error:
            # El error vuelve al modelo para que corrija la llamada.
            return {"error": f"Error ejecutando {pedido.name}: {error}"}
