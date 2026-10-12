"""Dashboard ejecutivo interactivo en Streamlit para el Pronóstico de Costos de Equipos.

Integra:
- Visualización interactiva de pronósticos y modelos econométricos (BigQuery).
- Simulador de sensibilidad ('What-if') ante choques de materias primas.
- Agente Inteligente (Gemini Flash Lite) consumido a través de Apigee X.
"""

from __future__ import annotations

import json
import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# Configuración de página
st.set_page_config(
    page_title="Costos de Equipos | FinOps & Pronóstico AI",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos personalizados
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E293B; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.05rem; color: #64748B; margin-bottom: 1.5rem; }
    .metric-card { background: #F8FAFC; border-radius: 8px; padding: 16px; border-left: 4px solid #3B82F6; }
    .stTabs [data-baseweb="tab-list"] { gap: 16px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.05rem; font-weight: 600; padding: 10px 20px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Variables de entorno por defecto
PROYECTO_PROD = os.getenv("GOOGLE_CLOUD_PROJECT", "prueba-prod-511304")
BQ_DATASET = os.getenv("BQ_DATASET", f"{PROYECTO_PROD}.costos")
APIGEE_DEFAULT_URL = os.getenv("APIGEE_URL", "https://34.117.2.228.nip.io/v1/costos")
APIGEE_DEFAULT_KEY = os.getenv("APIGEE_API_KEY", "")
RESULTADOS_LOCALES = os.getenv("RESULTADOS_URI", "Resultados")


# -------------------------------------------------------------
# Funciones de Datos (BigQuery o, si no hay acceso, la carpeta local de resultados)
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def cargar_pronosticos_bq(dataset: str) -> pd.DataFrame:
    """Carga los pronósticos calculados desde BigQuery."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=dataset.split(".")[0])
        query = f"""
            SELECT equipo, fecha, h, p5, p50, p95, ancho_pct, dentro_horizonte
            FROM `{dataset}.pronostico`
            ORDER BY equipo, fecha
        """
        rows = [dict(row.items()) for row in client.query(query).result()]
        df = pd.DataFrame(rows)
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"])
        return df
    except Exception as e:
        st.warning(
            f"No se pudo consultar BigQuery ({e}). Se muestran los resultados locales de `{RESULTADOS_LOCALES}/`."
        )
        # Respaldo: los archivos que escribe `make pipeline`
        return pd.read_csv(f"{RESULTADOS_LOCALES}/pronostico.csv", parse_dates=["fecha"])


@st.cache_data(ttl=300)
def cargar_modelos_bq(dataset: str) -> dict:
    """Carga el resumen de los modelos ajustados desde BigQuery."""
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=dataset.split(".")[0])
        query = f"SELECT * FROM `{dataset}.modelo_final`"
        rows = [dict(row.items()) for row in client.query(query).result()]
        modelos = {}
        for fila in rows:
            coefs = fila["coeficientes"]
            ult_p = fila["ultimos_precios"]
            modelos[fila["equipo"]] = {
                "variables": fila["variables"].split("+"),
                "coeficientes": json.loads(coefs) if isinstance(coefs, str) else coefs,
                "r2": float(fila["r2"]),
                "mape": float(fila["mape_prueba"]),
                "ultimo_mes": fila["ultimo_mes"],
                "ultimos_precios": json.loads(ult_p) if isinstance(ult_p, str) else ult_p,
            }
        return modelos
    except Exception:
        # Respaldo: el modelo que escribe `make pipeline`
        with open(f"{RESULTADOS_LOCALES}/modelo_final.json", encoding="utf-8") as archivo:
            locales = json.load(archivo)
        return {
            equipo: {
                "variables": m["variables"],
                "coeficientes": m["coeficientes"],
                "r2": m["r2"],
                "mape": m["mape_prueba"],
                "ultimo_mes": m["ultimo_mes"],
                "ultimos_precios": m["ultimos_precios"],
            }
            for equipo, m in locales.items()
        }


# -------------------------------------------------------------
# Barra Lateral (Configuración y Gobernanza)
# -------------------------------------------------------------
with st.sidebar:
    st.image("https://www.gstatic.com/images/branding/product/2x/google_cloud_64dp.png", width=48)
    st.title("Gobernanza & Red")
    st.caption("Plataforma de Producción GCP")

    st.markdown("---")
    st.subheader("🔌 Conexión a Apigee X")
    apigee_url = st.text_input("Endpoint del Gateway", value=APIGEE_DEFAULT_URL)
    api_key = st.text_input("API Key (app-costos)", value=APIGEE_DEFAULT_KEY, type="password")

    if st.button("Probar Conexión (`/salud`)", use_container_width=True):
        if not api_key:
            st.error("Por favor ingresa tu API Key.")
        else:
            try:
                res = requests.get(f"{apigee_url}/salud?apikey={api_key}", verify=False, timeout=5)
                if res.status_code == 200:
                    st.success("✅ Conectado a Apigee X con éxito (200 OK)")
                else:
                    st.error(f"Error {res.status_code}: {res.text[:100]}")
            except Exception as ex:
                st.error(f"Fallo de conexión: {ex}")

    st.markdown("---")
    st.subheader("🏗️ Infraestructura")
    st.markdown(f"""
    - **Proyecto:** `{PROYECTO_PROD}`
    - **Región:** `us-central1`
    - **Dataset BQ:** `{BQ_DATASET}`
    - **LLM:** `Gemini 3.1 Flash Lite`
    """)


# -------------------------------------------------------------
# Encabezado Principal
# -------------------------------------------------------------
st.markdown('<div class="main-header">Pronóstico de Costos de Equipos</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Solución Empresarial: Simulación Monte Carlo + BigQuery Data Warehouse + Agente Gemini + Apigee API Management</div>',
    unsafe_allow_html=True,
)

# Cargar datos
df_pronosticos = cargar_pronosticos_bq(BQ_DATASET)
modelos = cargar_modelos_bq(BQ_DATASET)

equipos_disponibles = list(df_pronosticos["equipo"].unique()) if not df_pronosticos.empty else ["Equipo1", "Equipo2"]

# Tabs de navegación
tab1, tab2, tab3 = st.tabs(["📈 Pronóstico & Modelos", "🧪 Simulador 'What-If'", "🤖 Agente Inteligente (Gemini)"])


# -------------------------------------------------------------
# TAB 1: Pronóstico y Modelos Econométricos
# -------------------------------------------------------------
with tab1:
    col_sel, col_vacia = st.columns([2, 4])
    with col_sel:
        equipo_sel = st.selectbox("Selecciona el Equipo a analizar:", options=equipos_disponibles, index=0)

    df_eq = df_pronosticos[df_pronosticos["equipo"] == equipo_sel].sort_values("fecha")
    modelo_eq = modelos.get(equipo_sel, {})

    # Tarjetas de KPIs
    if not df_eq.empty:
        p_inmediato = df_eq.iloc[0]
        h_confiable = int(df_eq["dentro_horizonte"].sum())

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric(
                label=f"Pronóstico Próximo Mes ({p_inmediato['fecha'].strftime('%Y-%m')})",
                value=f"${p_inmediato['p50']:,.2f} USD",
                delta="p50 (Mediana)",
            )
        with kpi2:
            ancho_usd = p_inmediato["p95"] - p_inmediato["p5"]
            st.metric(
                label="Intervalo de Confianza 90%",
                value=f"${p_inmediato['p5']:,.0f} - ${p_inmediato['p95']:,.0f}",
                delta=f"±{ancho_usd/2:,.1f} USD",
                delta_color="inverse",
            )
        with kpi3:
            st.metric(
                label="Horizonte Recomendado",
                value=f"{h_confiable} meses",
                delta="Incertidumbre ≤ 30%" if h_confiable > 0 else "Alta dispersión",
            )
        with kpi4:
            r2 = modelo_eq.get("r2", 0.94)
            st.metric(
                label="Precisión del Modelo (R²)",
                value=f"{r2*100:.1f}%",
                delta=f"Variables: {', '.join(modelo_eq.get('variables', ['X', 'Y']))}",
            )

    st.markdown("---")

    # Gráfica interactiva con Plotly
    st.subheader(f"Curva de Pronóstico con Intervalos de Monte Carlo ({equipo_sel})")

    fig = go.Figure()

    # Intervalo de confianza p5 - p95 sombreado
    fig.add_trace(
        go.Scatter(
            x=df_eq["fecha"],
            y=df_eq["p95"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            name="p95 (Límite Superior)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_eq["fecha"],
            y=df_eq["p5"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(59, 130, 246, 0.2)",
            name="Intervalo 90% (p5 a p95)",
        )
    )

    # Mediana p50
    fig.add_trace(
        go.Scatter(
            x=df_eq["fecha"],
            y=df_eq["p50"],
            mode="lines+markers",
            line=dict(color="#2563EB", width=3),
            marker=dict(size=8),
            name="Pronóstico p50 (Mediana)",
        )
    )

    # Marcar límite del horizonte recomendado
    if df_eq["dentro_horizonte"].any():
        limite_h = df_eq[df_eq["dentro_horizonte"]]["fecha"].max()
        fig.add_vline(
            x=limite_h,
            line_dash="dash",
            line_color="#DC2626",
            annotation_text="Límite Horizonte Confiable",
            annotation_position="top left",
        )

    fig.update_layout(
        title=f"Evolución proyectada de {equipo_sel} en los próximos {len(df_eq)} meses",
        xaxis_title="Mes",
        yaxis_title="Costo Unitario (USD)",
        hovermode="x unified",
        template="plotly_white",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabla de datos
    with st.expander("Ver tabla completa de pronósticos y dispersión"):
        st.dataframe(
            df_eq.style.format({
                "p5": "${:,.2f}",
                "p50": "${:,.2f}",
                "p95": "${:,.2f}",
                "ancho_pct": "{:.1f} %",
            }),
            use_container_width=True,
        )


# -------------------------------------------------------------
# TAB 2: Simulador de Sensibilidad ("What-If")
# -------------------------------------------------------------
with tab2:
    st.subheader("Simulación de Escenarios de Mercado ante Variaciones de Materias Primas")
    st.markdown(
        "Utiliza los deslizadores para proyectar el impacto en USD que tendría un cambio de precios en el mercado internacional."
    )

    col_sim_eq, col_vacia2 = st.columns([2, 4])
    with col_sim_eq:
        sim_equipo = st.selectbox("Equipo para la simulación:", options=equipos_disponibles, key="sim_eq")

    m_info = modelos.get(sim_equipo, {})
    vars_modelo = m_info.get("variables", ["X", "Y"])
    coefs = m_info.get("coeficientes", {})
    ultimos_p = m_info.get("ultimos_precios", {})

    st.markdown("#### Variación Porcentual Simulada (%)")
    col_x, col_y, col_z = st.columns(3)

    with col_x:
        delta_x = st.slider("Materia Prima X", min_value=-40, max_value=40, value=10, step=5, format="%d%%")
    with col_y:
        delta_y = st.slider("Materia Prima Y", min_value=-40, max_value=40, value=0, step=5, format="%d%%")
    with col_z:
        delta_z = st.slider("Materia Prima Z", min_value=-40, max_value=40, value=0, step=5, format="%d%%")

    deltas = {"X": delta_x, "Y": delta_y, "Z": delta_z}

    # Cálculo de impactos
    impacto_total = 0.0
    filas_impacto = []

    for mp, delta in deltas.items():
        if mp in vars_modelo:
            precio_base = ultimos_p.get(mp, 100.0)
            coef = coefs.get(mp, 0.0)
            impacto = coef * precio_base * (delta / 100.0)
            impacto_total += impacto
            filas_impacto.append({
                "Materia Prima": mp,
                "Precio Base": f"${precio_base:,.2f} USD",
                "Variación Simulada": f"{delta:+d}%",
                "Coeficiente del Modelo": round(coef, 4),
                "Impacto en el Costo": round(impacto, 2),
            })
        else:
            filas_impacto.append({
                "Materia Prima": mp,
                "Precio Base": f"${ultimos_p.get(mp, 0.0):,.2f} USD",
                "Variación Simulada": f"{delta:+d}%",
                "Coeficiente del Modelo": 0.0,
                "Impacto en el Costo": 0.0,
            })

    # Métricas del escenario
    st.markdown("---")
    r1, r2 = st.columns([2, 4])
    with r1:
        st.metric(
            label=f"Impacto Neto Proyectado ({sim_equipo})",
            value=f"${impacto_total:+,.2f} USD",
            delta="Aumento de costo" if impacto_total > 0 else "Ahorro de costo",
            delta_color="inverse" if impacto_total > 0 else "normal",
        )
    with r2:
        st.dataframe(pd.DataFrame(filas_impacto), use_container_width=True)


# -------------------------------------------------------------
# TAB 3: Agente Inteligente (Gemini + Apigee)
# -------------------------------------------------------------
with tab3:
    st.subheader("Asistente Virtual de Costos (Gemini 3.1 Flash Lite)")
    st.caption("Interactúa mediante lenguaje natural. El agente consulta BigQuery y herramientas estadísticas a través de Apigee X.")

    # Inicializar historial de chat en sesión
    if "mensajes" not in st.session_state:
        st.session_state["mensajes"] = [
            {
                "role": "assistant",
                "content": "¡Hola! Soy tu asistente de análisis de costos. Puedo consultar pronósticos a futuro, explicar modelos de regresión o simular escenarios de variación de materias primas. ¿Qué deseas consultar?",
            }
        ]

    # Mostrar mensajes existentes
    for msg in st.session_state["mensajes"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "finops" in msg:
                st.caption(f"📊 FinOps: {msg['finops']}")

    # Input del usuario
    if prompt := st.chat_input("Ej: ¿Cuánto costará el Equipo 1 en octubre de 2023 y qué materias primas lo mueven?"):
        # Agregar mensaje del usuario
        st.session_state["mensajes"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Llamar al Agente a través de Apigee
        with st.chat_message("assistant"):
            if not api_key:
                mensaje_error = "⚠️ Por favor ingresa tu API Key en la barra lateral para consultar a través de Apigee."
                st.warning(mensaje_error)
                st.session_state["mensajes"].append({"role": "assistant", "content": mensaje_error})
            else:
                with st.spinner("Consultando al Agente a través de Apigee X..."):
                    try:
                        url_api = f"{apigee_url}/preguntar?apikey={api_key}"
                        payload = {"pregunta": prompt}
                        headers = {"Content-Type": "application/json", "X-Consumidor": "dashboard-streamlit"}

                        resp = requests.post(url_api, json=payload, headers=headers, verify=False, timeout=30)

                        if resp.status_code == 200:
                            data = resp.json()
                            respuesta_texto = data.get("respuesta", "Sin respuesta.")
                            uso = data.get("uso", {})
                            tokens = uso.get("tokens_totales", 0)
                            costo = uso.get("costo_usd", 0.0)
                            finops_str = f"Tokens: {tokens:,} | Costo Estimado: ${costo:.6f} USD"

                            st.markdown(respuesta_texto)
                            st.caption(f"📊 FinOps: {finops_str}")

                            st.session_state["mensajes"].append({
                                "role": "assistant",
                                "content": respuesta_texto,
                                "finops": finops_str,
                            })
                        elif resp.status_code == 429:
                            st.error("⚠️ Error 429: Spike Arrest activo en Apigee (límite de ráfagas excedido). Espera 6 segundos.")
                        else:
                            st.error(f"Error {resp.status_code} desde Apigee: {resp.text}")
                    except Exception as err:
                        st.error(f"Error de conexión con el agente: {err}")
