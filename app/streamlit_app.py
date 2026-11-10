"""Minuta: Aplicación Streamlit optimizada para dispositivos móviles (T06).

Alternativa económica a grabadoras de hardware con IA (como Plaud) que usa tu celular.
Graba una ponencia, clase, reunión o entrevista, y genera:
- Transcripción completa con marcas de tiempo.
- Resumen ejecutivo estructurado.
- Mapa mental interactivo con markmap.js.
- Lista de acuerdos y to-do con citas textuales verificables.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from minuta.detector import DetectorSegmentos
from minuta.esquemas import (
    NodoMapa,
    MapaMental,
    ResultadoPonencia,
    ResultadoReunion,
    ResultadoEntrevista,
    Transcripcion,
)
from minuta.estructurar import estructurar_transcripcion, TipoPlantilla
from minuta.exportar import (
    exportar_docx,
    exportar_mapa_html,
    exportar_markdown,
    exportar_xlsx,
    exportar_transcripcion_texto,
)
from minuta.proveedores import ProveedorGemini, ProveedorMock, ProveedorOllama, ProveedorLLM
from minuta.transcribir import transcribir_audio

# Versión exacta y verificada de markmap-autoloader en CDN jsDelivr
VERSION_MARKMAP_CDN = "0.17.2"

PLANTILLAS_DISPONIBLES = [
    "Ponencia / Clase / Charla",
    "Reunión",
    "Entrevista",
]

GLOSARIO_DEFECTO = [
    "journal",
    "Scopus",
    "paper",
    "deadline",
    "peer review",
    "APC",
    "grant",
    "preprint",
    "publisher",
    "citation rate",
]

ARCHIVOS_FIXTURES: dict[str, tuple[str, str]] = {
    "Ponencia / Clase / Charla": ("resultado_ponencia.json", "transcripcion_ponencia.json"),
    "Reunión": ("resultado_reunion.json", "transcripcion_reunion.json"),
    "Entrevista": ("resultado_entrevista.json", "transcripcion_entrevista.json"),
}


def segundos_a_tiempo(segundos: float) -> str:
    """Convierte segundos a formato de visualización [mm:ss]."""
    seg = max(0, int(round(segundos)))
    minutos = seg // 60
    restantes = seg % 60
    return f"[{minutos:02d}:{restantes:02d}]"


def generar_html_markmap(markdown_arbol: str, altura_px: int = 480) -> str:
    """Genera el documento HTML autónomo con markmap-autoloader para renderizado interactivo."""
    # Escapar cierre de script para evitar romper el template HTML
    markdown_seguro = markdown_arbol.replace("</script>", "<\\/script>")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background-color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .markmap-container {{
      position: relative;
      width: 100%;
      height: {altura_px}px;
      border: 1px solid #e9ecef;
      border-radius: 8px;
      background: #fafbfc;
    }}
    .markmap {{
      width: 100%;
      height: 100%;
    }}
    .markmap > svg {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    .markmap-help {{
      position: absolute;
      bottom: 8px;
      right: 12px;
      font-size: 11px;
      color: #6c757d;
      background: rgba(255, 255, 255, 0.85);
      padding: 2px 6px;
      border-radius: 4px;
      pointer-events: none;
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@{VERSION_MARKMAP_CDN}"></script>
</head>
<body>
  <div class="markmap-container">
    <div class="markmap">
      <script type="text/template">
{markdown_seguro}
      </script>
    </div>
    <div class="markmap-help">Pellizca para zoom · Arrastra para mover</div>
  </div>
  <script>
    function renderizarMapa() {{
      if (window.markmap && window.markmap.autoLoader) {{
        window.markmap.autoLoader.renderAll();
      }}
    }}
    window.addEventListener("DOMContentLoaded", renderizarMapa);
    window.addEventListener("load", renderizarMapa);
    if (document.readyState === "complete" || document.readyState === "interactive") {{
      setTimeout(renderizarMapa, 50);
    }}
  </script>
</body>
</html>"""


def extraer_nodos_con_tiempo(raiz: NodoMapa) -> list[dict[str, Any]]:
    """Extrae recursivamente todos los nodos del árbol que poseen evidencia temporal."""
    resultados: list[dict[str, Any]] = []

    def _recorrer(nodo: NodoMapa) -> None:
        if nodo.evidencia is not None:
            tag = nodo.tiempo_tag() or segundos_a_tiempo(nodo.evidencia.inicio_s)
            resultados.append({
                "id": nodo.id,
                "titulo": nodo.titulo,
                "resumen": nodo.resumen,
                "inicio_s": nodo.evidencia.inicio_s,
                "tiempo_tag": tag,
                "cita": nodo.evidencia.cita,
                "segmento_ids": nodo.evidencia.segmento_ids,
            })
        for hijo in nodo.hijos:
            _recorrer(hijo)

    _recorrer(raiz)
    resultados.sort(key=lambda x: x["inicio_s"])
    return resultados


def cargar_fixture_demo(plantilla: str) -> tuple[Any, Transcripcion | None]:
    """Carga y valida los fixtures locales de data/fixtures/ según la plantilla seleccionada."""
    if plantilla not in ARCHIVOS_FIXTURES:
        raise ValueError(f"Plantilla no reconocida: {plantilla}")

    archivo_res, archivo_trans = ARCHIVOS_FIXTURES[plantilla]
    ruta_base = Path(__file__).resolve().parent.parent / "data" / "fixtures"

    ruta_res = ruta_base / archivo_res
    ruta_trans = ruta_base / archivo_trans

    if not ruta_res.exists():
        raise FileNotFoundError(f"Fixture no encontrado en: {ruta_res}")

    with open(ruta_res, "r", encoding="utf-8") as f:
        datos_res = json.load(f)

    if plantilla == "Ponencia / Clase / Charla":
        resultado = ResultadoPonencia.model_validate(datos_res)
    elif plantilla == "Reunión":
        resultado = ResultadoReunion.model_validate(datos_res)
    elif plantilla == "Entrevista":
        resultado = ResultadoEntrevista.model_validate(datos_res)
    else:
        raise ValueError(f"Plantilla no soportada: {plantilla}")

    transcripcion: Transcripcion | None = None
    if ruta_trans.exists():
        with open(ruta_trans, "r", encoding="utf-8") as f:
            datos_trans = json.load(f)
        transcripcion = Transcripcion.model_validate(datos_trans)

    return resultado, transcripcion


def aplicar_estilos_movil() -> None:
    """Inyecta reglas CSS optimizadas para dispositivos móviles con botones táctiles grandes."""
    st.markdown(
        """
        <style>
        /* Optimización Mobile-First para Minuta */
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
            max-width: 680px;
        }
        /* Botones táctiles accesibles (mínimo 48px para dedos) */
        .stButton > button {
            width: 100%;
            min-height: 48px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 10px;
            margin-top: 4px;
            margin-bottom: 4px;
        }
        /* Pestañas legibles en móvil */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            display: flex;
            flex-wrap: wrap;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px;
            font-size: 14px;
            font-weight: 500;
        }
        /* Tarjetas de contenido con citas */
        .minuta-card {
            background-color: #F8F9FA;
            border: 1px solid #E9ECEF;
            border-radius: 8px;
            padding: 12px 14px;
            margin-bottom: 10px;
        }
        .minuta-badge {
            display: inline-block;
            padding: 2px 7px;
            font-size: 12px;
            font-weight: 700;
            color: #0D6EFD;
            background-color: #E7F1FF;
            border-radius: 5px;
            margin-right: 6px;
        }
        .minuta-badge-sec {
            display: inline-block;
            padding: 2px 7px;
            font-size: 12px;
            font-weight: 600;
            color: #495057;
            background-color: #E9ECEF;
            border-radius: 5px;
            margin-right: 6px;
        }
        .minuta-quote {
            border-left: 3px solid #0D6EFD;
            padding-left: 8px;
            margin-top: 6px;
            font-style: italic;
            color: #495057;
            font-size: 13.5px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """Punto de entrada de la aplicación Streamlit."""
    st.set_page_config(
        page_title="Minuta - Alternativa a Plaud con tu Celular",
        page_icon="🎙️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    aplicar_estilos_movil()

    # Inicialización de estado en sesión
    if "reproductor_inicio_s" not in st.session_state:
        st.session_state["reproductor_inicio_s"] = 0.0
    if "glosario_usuario" not in st.session_state:
        st.session_state["glosario_usuario"] = ", ".join(GLOSARIO_DEFECTO)

    # Encabezado principal
    st.title("🎙️ Minuta")
    st.caption("Tu alternativa económica a las grabadoras con IA (como Plaud) usando tu celular.")

    # 1. Guía de grabación visible
    st.info(
        "📱 **Guía de grabación con celular:**\n\n"
        "Graba con la grabadora de voz nativa del celular (preferentemente en **modo avión** "
        "para charlas largas) y sube el archivo aquí."
    )

    # 2. Configuración y subida en acordeón o bloques limpios
    with st.expander("⚙️ Configuración y Glosario", expanded=False):
        plantilla = st.selectbox(
            "Plantilla de análisis:",
            options=PLANTILLAS_DISPONIBLES,
            index=0,
            help="Selecciona el formato adecuado según la naturaleza del audio.",
        )

        glosario_texto = st.text_area(
            "Glosario contextual de investigación:",
            value=st.session_state["glosario_usuario"],
            help="Términos técnicos en inglés o español que deben ser reconocidos con precisión.",
            height=75,
        )
        st.session_state["glosario_usuario"] = glosario_texto

        modo_demo = st.toggle(
            "🧪 Modo Demo (cargar datos precalculados sin red)",
            value=True,
            help="Carga fixtures locales instantáneamente sin llamar a modelos ni consumir cuota.",
        )

        proveedor_seleccionado = st.selectbox(
            "Proveedor de IA para estructuración:",
            options=["Gemini 3.8 Flash (Nube)", "Ollama local (qwen3:4b)"],
            index=0,
            help="Selecciona el motor de lenguaje para estructurar el resumen y mapa mental.",
        )
        modo_analisis = st.radio(
            "Modo de análisis:",
            options=["detector", "solo_llm"],
            index=0,
            format_func=lambda m: "Detector mmBERT + LLM (Ahorro de tokens)" if m == "detector" else "Solo LLM directo",
            help="El detector filtra relleno acústico y prioriza tareas antes de consultar al LLM.",
        )
        modelo_whisper = st.selectbox(
            "Modelo de transcripción Whisper:",
            options=["small", "base"],
            index=0,
            help="small para mayor fidelidad acústica en laptop; base para bajo consumo de memoria.",
        )

    # Si no está en el expander, se muestra la plantilla seleccionada actualmente
    if "plantilla" not in locals():
        plantilla = "Ponencia / Clase / Charla"
    if "modo_demo" not in locals():
        modo_demo = True

    # Clave de plantilla normalizada
    clave_slug: str = "ponencia" if plantilla == "Ponencia / Clase / Charla" else ("reunion" if plantilla == "Reunión" else "entrevista")

    # 3. Carga de audio
    st.subheader("1. Audio de la sesión")

    # Opción condicional si la versión de streamlit soporta st.audio_input
    if hasattr(st, "audio_input"):
        st.write("Graba un audio directo:")
        audio_grabado = getattr(st, "audio_input")("Grabar audio con el micrófono")
    else:
        audio_grabado = None

    archivo_audio = st.file_uploader(
        "Sube tu archivo de audio (grabado con el celular):",
        type=["m4a", "mp3", "wav"],
        help="Formatos soportados: m4a, mp3, wav. Máximo 200 MB.",
    )

    fuente_audio = archivo_audio or audio_grabado

    # 4. Procesamiento o carga de datos
    resultado: Any = None
    transcripcion: Transcripcion | None = None

    if modo_demo:
        st.success(f"⚡ Modo Demo activo: Mostrando datos precalculados de **{plantilla}**.")
        try:
            resultado, transcripcion = cargar_fixture_demo(plantilla)
        except Exception as err:
            st.error(f"Error al cargar fixture de demo: {err}")
            return
    else:
        if fuente_audio is None:
            st.warning("👈 Por favor sube un archivo de audio o activa el Modo Demo para ver un ejemplo inmediato.")
            return

        boton_procesar = st.button("🚀 Procesar Audio con Minuta", type="primary")
        if boton_procesar:
            with st.status("Procesando audio con Minuta...", expanded=True) as status_box:
                st.write("🎙️ 1/3: Transcribiendo audio con faster-whisper...")
                nombre_archivo = getattr(fuente_audio, "name", "audio.m4a")
                sufijo = Path(nombre_archivo).suffix or ".m4a"
                with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as tmp_file:
                    tmp_file.write(fuente_audio.getvalue())
                    tmp_path = tmp_file.name

                try:
                    glosario_lista = [t.strip() for t in glosario_texto.split(",") if t.strip()]
                    transcripcion = transcribir_audio(
                        tmp_path,
                        modelo=modelo_whisper,
                        glosario_adicional=glosario_lista,
                    )
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass

                st.write("🧠 2/3: Clasificando y filtrando segmentos con mmBERT...")
                detector = DetectorSegmentos() if modo_analisis == "detector" else None

                st.write("✨ 3/3: Estructurando mapa mental, resumen y to-dos con IA...")
                clave_plantilla: TipoPlantilla = clave_slug  # type: ignore

                proveedor: ProveedorLLM
                if "Gemini" in proveedor_seleccionado:
                    api_key = os.getenv("GEMINI_API_KEY")
                    if not api_key:
                        try:
                            api_key = st.secrets.get("GEMINI_API_KEY")
                        except Exception:
                            api_key = None
                    if api_key:
                        proveedor = ProveedorGemini(api_key=api_key)
                    else:
                        st.warning("GEMINI_API_KEY no detectada. Empleando proveedor de demostración offline.")
                        proveedor = ProveedorMock()
                else:
                    proveedor = ProveedorOllama()

                resultado = estructurar_transcripcion(
                    transcripcion=transcripcion,
                    tipo_plantilla=clave_plantilla,
                    proveedor=proveedor,
                    modo=modo_analisis,
                    detector=detector,
                )

                st.session_state["resultado_procesado"] = resultado
                st.session_state["transcripcion_procesada"] = transcripcion
                status_box.update(label="¡Procesamiento completado con éxito!", state="complete", expanded=False)

        if "resultado_procesado" in st.session_state and fuente_audio is not None:
            resultado = st.session_state["resultado_procesado"]
            transcripcion = st.session_state.get("transcripcion_procesada")
        elif not boton_procesar:
            st.info("Presiona **🚀 Procesar Audio con Minuta** para iniciar la transcripción y estructuración.")
            return

    if resultado is None:
        return

    # 5. Reproductor sincronizado con marcas de tiempo
    st.subheader("2. Reproductor y minuto")

    inicio_actual = float(st.session_state.get("reproductor_inicio_s", 0.0))

    if fuente_audio is not None:
        st.audio(fuente_audio, start_time=int(inicio_actual))
        st.caption(f"Posición actual del reproductor: {segundos_a_tiempo(inicio_actual)}")
    else:
        # En modo demo sin audio subido por la regla de privacidad L21
        st.markdown(
            f"""
            <div class="minuta-card">
              <span class="minuta-badge">MODO DEMO</span>
              <strong>Posición de reproducción:</strong> {segundos_a_tiempo(inicio_actual)}<br>
              <small style="color: #6c757d;">
                🔒 <em>Regla de privacidad: La demo pública no almacena audio real.
                Al pulsar ▶ en un nodo, el minutero se actualiza a su marca de tiempo exacta.</em>
              </small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 6. Pestañas organizadas según la plantilla (L45)
    st.subheader("3. Resultados estructurados")

    # Renderizado condicional según el tipo de plantilla
    if isinstance(resultado, ResultadoPonencia):
        pestana_notas, pestana_mapa, pestana_trans = st.tabs([
            "📝 Notas de clase",
            "🗺️ Mapa mental",
            "📄 Transcripción completa",
        ])

        with pestana_notas:
            st.markdown("### Resumen General")
            st.write(resultado.resumen_general)

            st.markdown("### Ideas Clave")
            for idea in resultado.ideas_clave:
                st.markdown(f"**• {idea.titulo}**")
                st.write(idea.resumen)
                for ev in idea.evidencias:
                    tag = segundos_a_tiempo(ev.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_idea_{ev.inicio_s}_{ev.cita[:10]}"):
                            st.session_state["reproductor_inicio_s"] = ev.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f'<div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(ev.cita)}"</div>',
                            unsafe_allow_html=True,
                        )

            st.markdown("### ❓ Preguntas del Público y Pendientes")
            if resultado.preguntas:
                for p in resultado.preguntas:
                    tag = segundos_a_tiempo(p.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_preg_{p.evidencia.inicio_s}_{p.descripcion[:10]}"):
                            st.session_state["reproductor_inicio_s"] = p.evidencia.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f"""
                            <div class="minuta-card">
                              <strong>? {html.escape(p.descripcion)}</strong>
                              <div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(p.evidencia.cita)}"</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.info("No se identificaron preguntas abiertas en la sesión.")

        with pestana_mapa:
            st.markdown(f"**Árbol temático interactivo:** *{resultado.mapa.titulo}*")
            html_mapa = generar_html_markmap(resultado.mapa.to_markdown(), altura_px=460)
            components.html(html_mapa, height=480, scrolling=False)

            st.markdown("#### Nodos del mapa con marca temporal y cita literal")
            nodos_tiempo = extraer_nodos_con_tiempo(resultado.mapa.raiz)

            for nodo in nodos_tiempo:
                col_tiempo, col_titulo = st.columns([1, 3])
                with col_tiempo:
                    boton_label = f"▶ {nodo['tiempo_tag']}"
                    if st.button(boton_label, key=f"btn_nodo_{nodo['id']}"):
                        st.session_state["reproductor_inicio_s"] = nodo["inicio_s"]
                        st.rerun()
                with col_titulo:
                    st.markdown(f"**{nodo['titulo']}**")
                    if nodo["resumen"]:
                        st.write(nodo["resumen"])
                    st.markdown(
                        f'<div class="minuta-quote">"{html.escape(nodo["cita"])}"</div>',
                        unsafe_allow_html=True,
                    )
                st.divider()

    elif isinstance(resultado, ResultadoReunion):
        # En plantilla Reunión: NO hay pestaña ni componente de mapa mental (L45)
        pestana_notas, pestana_trans = st.tabs([
            "📝 Notas de reunión",
            "📄 Transcripción completa",
        ])

        with pestana_notas:
            st.markdown("### Resumen General")
            st.write(resultado.resumen_general)

            st.markdown("### Temas Tratados")
            for tema in resultado.temas:
                st.markdown(f"**• {tema.titulo}**")
                st.write(tema.resumen)
                for ev in tema.evidencias:
                    tag = segundos_a_tiempo(ev.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_tema_{ev.inicio_s}_{ev.cita[:10]}"):
                            st.session_state["reproductor_inicio_s"] = ev.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f'<div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(ev.cita)}"</div>',
                            unsafe_allow_html=True,
                        )

            st.markdown("### 🤝 Acuerdos")
            if resultado.acuerdos:
                for a in resultado.acuerdos:
                    tag = segundos_a_tiempo(a.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_acuerdo_{a.evidencia.inicio_s}_{a.descripcion[:10]}"):
                            st.session_state["reproductor_inicio_s"] = a.evidencia.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f"""
                            <div class="minuta-card">
                              <strong>• {html.escape(a.descripcion)}</strong>
                              <div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(a.evidencia.cita)}"</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.info("No se registraron acuerdos formales.")

            st.markdown("### ✅ Tareas (To-Do)")
            if resultado.tareas:
                for t in resultado.tareas:
                    resp = f" — Responsable: **{t.responsable}**" if t.responsable else ""
                    limite = f" (Límite: {t.fecha_limite})" if t.fecha_limite else ""
                    tag = segundos_a_tiempo(t.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_tarea_{t.evidencia.inicio_s}_{t.descripcion[:10]}"):
                            st.session_state["reproductor_inicio_s"] = t.evidencia.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f"""
                            <div class="minuta-card">
                              <strong>☑ {html.escape(t.descripcion)}</strong>{resp}{limite}<br>
                              <div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(t.evidencia.cita)}"</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.info("No se registraron tareas pendientes.")

            st.markdown("### ❓ Preguntas y Pendientes")
            if resultado.pendientes:
                for p in resultado.pendientes:
                    tag = segundos_a_tiempo(p.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_pend_{p.evidencia.inicio_s}_{p.descripcion[:10]}"):
                            st.session_state["reproductor_inicio_s"] = p.evidencia.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f"""
                            <div class="minuta-card">
                              <strong>? {html.escape(p.descripcion)}</strong>
                              <div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(p.evidencia.cita)}"</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
            else:
                st.info("No quedaron preguntas pendientes.")

    else:
        # En plantilla Entrevista: Esquema por temas en lista indentada sin diagrama markmap (L45)
        pestana_esquema, pestana_trans = st.tabs([
            "📑 Esquema por temas",
            "📄 Transcripción completa",
        ])

        with pestana_esquema:
            st.markdown("### Esquema Temático Jerárquico")
            st.caption("Estructura de la conversación en lista jerárquica con [mm:ss] y citas literales (sin diagrama markmap):")

            nodos_tiempo = extraer_nodos_con_tiempo(resultado.mapa.raiz)
            for nodo in nodos_tiempo:
                col_tiempo, col_titulo = st.columns([1, 3])
                with col_tiempo:
                    boton_label = f"▶ {nodo['tiempo_tag']}"
                    if st.button(boton_label, key=f"btn_esq_{nodo['id']}"):
                        st.session_state["reproductor_inicio_s"] = nodo["inicio_s"]
                        st.rerun()
                with col_titulo:
                    st.markdown(f"**{nodo['titulo']}**")
                    if nodo["resumen"]:
                        st.write(nodo["resumen"])
                    st.markdown(
                        f'<div class="minuta-quote">"{html.escape(nodo["cita"])}"</div>',
                        unsafe_allow_html=True,
                    )
                st.divider()

            st.markdown("### Resumen por Código Temático")
            for cod, res_cod in resultado.resumen_por_codigo.items():
                st.markdown(f"**• Código [{cod}]**")
                st.write(res_cod)

            st.markdown("### 📚 Libro de Códigos de Investigación")
            for c in resultado.libro:
                st.markdown(
                    f"""
                    <div class="minuta-card">
                      <span class="minuta-badge">CÓDIGO: {html.escape(c.codigo)}</span><br>
                      {html.escape(c.descripcion)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("### 🏷️ Fragmentos Codificados")
            for f in resultado.fragmentos:
                tag = segundos_a_tiempo(f.evidencia.inicio_s)
                col_t, col_c = st.columns([1, 4])
                with col_t:
                    if st.button(f"▶ {tag}", key=f"btn_frag_{f.evidencia.inicio_s}_{f.codigo}"):
                        st.session_state["reproductor_inicio_s"] = f.evidencia.inicio_s
                        st.rerun()
                with col_c:
                    nota_html = f"<br><small>Nota: {html.escape(f.nota)}</small>" if f.nota else ""
                    st.markdown(
                        f"""
                        <div class="minuta-card">
                          <span class="minuta-badge-sec">{html.escape(f.codigo)}</span>
                          <div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(f.evidencia.cita)}"</div>
                          {nota_html}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # PESTAÑA COMÚN: TRANSCRIPCIÓN COMPLETA
    with pestana_trans:
        if transcripcion is not None:
            st.markdown(
                f"**Duración total:** {segundos_a_tiempo(transcripcion.duracion_s)} "
                f"({int(transcripcion.duracion_s // 60)} min) · "
                f"**Segmentos:** {len(transcripcion.segmentos)} · "
                f"**Modelo:** `{transcripcion.modelo}`"
            )

            filtro_texto = st.text_input("🔍 Buscar término en transcripción:", value="").lower().strip()

            for seg in transcripcion.segmentos:
                if filtro_texto and filtro_texto not in seg.texto.lower():
                    continue
                tag_rango = f"{segundos_a_tiempo(seg.inicio_s)} → {segundos_a_tiempo(seg.fin_s)}"
                st.markdown(
                    f'<span class="minuta-badge">{tag_rango}</span> {html.escape(seg.texto)}',
                    unsafe_allow_html=True,
                )
                st.write("")
        else:
            st.info("No hay transcripción disponible para esta visualización.")

    # 7. Sección de Exportación (L45 / T14)
    st.divider()
    st.subheader("4. Exportar Minuta")
    st.caption("Descarga tus notas estructuradas, mapa mental o transcripción en el formato que prefieras:")

    es_clase = isinstance(resultado, ResultadoPonencia)
    cols = st.columns(5 if es_clase else 4)

    with cols[0]:
        try:
            datos_md = exportar_markdown(resultado, transcripcion=transcripcion)
            st.download_button(
                "📄 Markdown (.md)",
                data=datos_md,
                file_name=f"minuta_{clave_slug}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        except Exception as err:
            st.caption(f"Error MD: {err}")

    with cols[1]:
        try:
            datos_docx = exportar_docx(resultado, transcripcion=transcripcion)
            st.download_button(
                "📝 Word (.docx)",
                data=datos_docx,
                file_name=f"minuta_{clave_slug}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as err:
            st.caption(f"Error Word: {err}")

    with cols[2]:
        try:
            datos_xlsx = exportar_xlsx(resultado)
            st.download_button(
                "📊 Excel (.xlsx)",
                data=datos_xlsx,
                file_name=f"minuta_{clave_slug}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as err:
            st.caption(f"Error Excel: {err}")

    with cols[3]:
        if transcripcion is not None:
            texto_trans = exportar_transcripcion_texto(transcripcion)
            st.download_button(
                "📜 Transcripción (.txt)",
                data=texto_trans,
                file_name=f"transcripcion_{clave_slug}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        else:
            st.button("📜 Transcripción (.txt)", disabled=True, use_container_width=True)

    if es_clase and len(cols) > 4:
        with cols[4]:
            try:
                datos_html = exportar_mapa_html(resultado.mapa, titulo=f"Minuta - {resultado.mapa.titulo}")
                st.download_button(
                    "🌐 Mapa HTML (.html)",
                    data=datos_html,
                    file_name=f"mapa_{clave_slug}.html",
                    mime="text/html",
                    use_container_width=True,
                )
            except Exception as err:
                st.caption(f"Error HTML: {err}")


if __name__ == "__main__":
    main()
