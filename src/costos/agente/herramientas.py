"""Herramientas que el agente puede llamar. Todas son de solo lectura."""

from __future__ import annotations

import json

from costos import EQUIPOS, MATERIAS_PRIMAS
from costos.agente.repositorio import Repositorio


def _json(objeto) -> str:
    return json.dumps(objeto, ensure_ascii=False)


def _normalizar_equipo(eq: str) -> str:
    c = str(eq).replace(" ", "").strip()
    if "1" in c or c.lower() == "equipo1":
        return "Equipo1"
    if "2" in c or c.lower() == "equipo2":
        return "Equipo2"
    return eq


def crear_herramientas(repo: Repositorio) -> list:
    """Crea las herramientas ligadas a un repositorio de resultados.

    Son funciones de Python: el SDK arma la declaración que ve el modelo a partir de la
    firma y del docstring de cada una.
    """

    def consultar_pronostico(equipo: str, mes: str = "") -> str:
        """Devuelve el pronóstico mensual del costo de un equipo en USD: p5, p50, p95, ancho del intervalo y si el mes cae dentro del horizonte recomendado.

        Args:
            equipo: Equipo1 o Equipo2.
            mes: Mes en formato AAAA-MM. Vacío para todos los meses pronosticados.
        """
        equipo = _normalizar_equipo(equipo)
        if equipo not in EQUIPOS:
            return _json({"error": f"Equipo desconocido: {equipo}. Opciones: {EQUIPOS}"})
        filas = repo.pronostico(equipo, mes or None)
        if not filas and mes:
            # Fallback seguro: si el formato de mes no hizo match exacto, entrega todos los meses
            filas = repo.pronostico(equipo, None)
        if not filas:
            return _json({"error": "Sin datos para ese equipo"})
        return _json({"equipo": equipo, "unidad": "USD", "filas": filas})

    def consultar_modelo(equipo: str) -> str:
        """Devuelve el modelo que explica el costo de un equipo: materias primas elegidas, coeficientes, p-valores, R², error fuera de muestra y prueba de cointegración.

        Args:
            equipo: Equipo1 o Equipo2.
        """
        equipo = _normalizar_equipo(equipo)
        modelo = repo.modelo(equipo)
        if modelo is None:
            return _json({"error": f"Sin modelo para {equipo}. Opciones: {EQUIPOS}"})
        return _json(modelo)

    def simular_escenario(equipo: str, materia_prima: str, cambio_porcentual: float) -> str:
        """Estima cuánto cambia el costo de un equipo si una materia prima sube o baja un porcentaje desde su último precio observado, según los coeficientes del modelo.

        Args:
            equipo: Equipo1 o Equipo2.
            materia_prima: X, Y o Z.
            cambio_porcentual: Cambio del precio de la materia prima en porcentaje, por ejemplo 10 o -5.
        """
        equipo = _normalizar_equipo(equipo)
        mp = str(materia_prima).strip().upper()
        modelo = repo.modelo(equipo)
        if modelo is None or mp not in MATERIAS_PRIMAS:
            return _json({"error": "Equipo o materia prima desconocidos"})
        if mp not in modelo["variables"]:
            return _json(
                {
                    "equipo": equipo,
                    "materia_prima": mp,
                    "impacto_usd_por_equipo": 0.0,
                    "nota": "Esta materia prima no está en el modelo del equipo; su efecto estimado es nulo.",
                }
            )
        precio = modelo["ultimos_precios"][mp]
        coeficiente = modelo["coeficientes"][mp]
        impacto = coeficiente * precio * cambio_porcentual / 100
        return _json(
            {
                "equipo": equipo,
                "materia_prima": mp,
                "precio_base": precio,
                "mes_base": modelo["ultimo_mes"],
                "coeficiente": coeficiente,
                "cambio_porcentual": cambio_porcentual,
                "impacto_usd_por_equipo": round(impacto, 2),
                "supuesto": "El cambio se sostiene y las demás materias primas no se mueven.",
            }
        )

    return [consultar_pronostico, consultar_modelo, simular_escenario]
