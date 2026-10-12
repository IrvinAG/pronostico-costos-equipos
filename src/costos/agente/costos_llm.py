"""Costo de cada llamada al LLM a partir de los tokens que reporta la respuesta.

Los precios son los de lista de Gemini 3.1 Flash-Lite en octubre de 2026, en USD por millón
de tokens de texto. Fuente: https://ai.google.dev/gemini-api/docs/pricing. Ajústalos si cambian.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

MODELO_POR_DEFECTO = "gemini-3.1-flash-lite"

PRECIOS = {
    MODELO_POR_DEFECTO: {"entrada": 0.25, "lectura_cache": 0.025, "salida": 1.50},
}


def costo_usd(modelo: str, entrada: int, salida: int, lectura_cache: int = 0) -> float:
    """Costo de una llamada. `entrada` incluye los tokens leídos de caché, que tienen su propia tarifa."""
    precio = PRECIOS.get(modelo, PRECIOS[MODELO_POR_DEFECTO])
    tokens = (
        (entrada - lectura_cache) * precio["entrada"]
        + lectura_cache * precio["lectura_cache"]
        + salida * precio["salida"]
    )
    return tokens / 1_000_000


def registrar(evento: dict) -> None:
    """Una línea JSON por evento. Cloud Logging la guarda como jsonPayload."""
    print(json.dumps({"severity": "INFO", **evento}, ensure_ascii=False, default=str), flush=True)


@dataclass
class UsoAcumulado:
    """Suma el consumo de todas las llamadas al LLM que hace una pregunta."""

    modelo: str
    llamadas: int = 0
    entrada: int = 0
    lectura_cache: int = 0
    salida: int = 0
    costo: float = 0.0

    def agregar(self, metadatos) -> dict:
        """Suma el `usage_metadata` de una respuesta y devuelve el detalle de esa llamada."""
        entrada = int(getattr(metadatos, "prompt_token_count", 0) or 0)
        lectura = int(getattr(metadatos, "cached_content_token_count", 0) or 0)
        # Los tokens de razonamiento se cobran como salida.
        salida = int(getattr(metadatos, "candidates_token_count", 0) or 0) + int(
            getattr(metadatos, "thoughts_token_count", 0) or 0
        )
        costo = costo_usd(self.modelo, entrada, salida, lectura)

        self.llamadas += 1
        self.entrada += entrada
        self.lectura_cache += lectura
        self.salida += salida
        self.costo += costo
        return {
            "entrada": entrada,
            "lectura_cache": lectura,
            "salida": salida,
            "costo_usd": round(costo, 6),
        }

    def a_dict(self) -> dict:
        return {
            "modelo": self.modelo,
            "llamadas": self.llamadas,
            "tokens_entrada": self.entrada,
            "tokens_lectura_cache": self.lectura_cache,
            "tokens_salida": self.salida,
            "tokens_totales": self.entrada + self.salida,
            "costo_usd": round(self.costo, 6),
        }
