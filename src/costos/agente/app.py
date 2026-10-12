"""API del agente. Cloud Run la sirve con uvicorn y Apigee X la expone con llave."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from costos import EQUIPOS, __version__
from costos.agente.agente import Agente
from costos.agente.repositorio import Repositorio, crear_repositorio

app = FastAPI(title="Agente de costos de equipos", version=__version__)


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=3, max_length=2000)


@lru_cache
def obtener_repositorio() -> Repositorio:
    return crear_repositorio()


@lru_cache
def obtener_agente() -> Agente:
    return Agente(obtener_repositorio())


@app.get("/salud")
def salud() -> dict:
    return {"estado": "ok", "version": __version__}


@app.get("/pronostico")
def pronostico(
    equipo: Annotated[str, Query(description="Equipo1 o Equipo2")],
    repo: Annotated[Repositorio, Depends(obtener_repositorio)],
    mes: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", description="AAAA-MM")] = None,
) -> dict:
    """Consulta directa del pronóstico, sin LLM y sin costo de tokens."""
    if equipo not in EQUIPOS:
        raise HTTPException(status_code=400, detail=f"Equipo desconocido. Opciones: {EQUIPOS}")
    filas = repo.pronostico(equipo, mes)
    if not filas:
        raise HTTPException(status_code=404, detail="Sin datos para ese equipo y mes")
    return {"equipo": equipo, "filas": filas}


@app.post("/preguntar")
def preguntar(
    cuerpo: Pregunta,
    agente: Annotated[Agente, Depends(obtener_agente)],
    x_consumidor: Annotated[
        str, Header(description="Quién pregunta; con Apigee lo inyecta el proxy")
    ] = "anonimo",
) -> dict:
    """Pregunta en lenguaje natural. Responde con cifras de las herramientas y el costo de la consulta."""
    return agente.responder(cuerpo.pregunta, consumidor=x_consumidor)
