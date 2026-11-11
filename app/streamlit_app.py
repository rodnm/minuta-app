"""Minuta: Aplicación Streamlit optimizada para dispositivos móviles (T06).

Alternativa económica a grabadoras de hardware con IA (como Plaud) que usa tu celular.
Graba una ponencia, clase, reunión o entrevista, y genera:
- Transcripción completa con marcas de tiempo.
- Resumen ejecutivo estructurado.
- Mapa mental interactivo con markmap.js.
- Lista de acuerdos y to-do con citas textuales verificables.

Se lanza con ``streamlit run app/streamlit_app.py`` desde la raíz del repositorio.
"""

from __future__ import annotations

import html
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

# B1: `streamlit run app/streamlit_app.py` solo agrega app/ a sys.path.
# La raíz del repositorio debe estar en sys.path antes de importar el paquete minuta.
RAIZ_REPO = Path(__file__).resolve().parent.parent
if str(RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPO))

import requests  # noqa: E402
import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from minuta.detector import DetectorSegmentos  # noqa: E402
from minuta.esquemas import (  # noqa: E402
    NodoMapa,
    ResultadoPonencia,
    ResultadoReunion,
    ResultadoEntrevista,
    Transcripcion,
)
from minuta.estructurar import estructurar_transcripcion, TipoPlantilla  # noqa: E402
from minuta.exportar import (  # noqa: E402
    exportar_docx,
    exportar_mapa_html,
    exportar_markdown,
    exportar_xlsx,
    exportar_transcripcion_texto,
)
from minuta.proveedores import ProveedorGemini, ProveedorOllama, ProveedorLLM  # noqa: E402
from minuta.transcribir import cargar_modelo_whisper, transcribir_audio  # noqa: E402

logger = logging.getLogger(__name__)

# Versión exacta y verificada de markmap-autoloader en CDN jsDelivr
VERSION_MARKMAP_CDN = "0.17.2"

PLANTILLAS_DISPONIBLES = [
    "Ponencia / Clase / Charla",
    "Reunión",
    "Entrevista",
]

SLUG_POR_PLANTILLA: dict[str, str] = {
    "Ponencia / Clase / Charla": "ponencia",
    "Reunión": "reunion",
    "Entrevista": "entrevista",
}

PROVEEDOR_GEMINI = "Gemini 3.8 Flash (Nube)"
PROVEEDOR_OLLAMA = "Ollama local (qwen3:4b)"

ETIQUETAS_MODO_ANALISIS: dict[str, str] = {
    "solo_llm": "Solo LLM",
    "detector": "Detector mmBERT + LLM (en desarrollo)",
}

OLLAMA_HOST_DEFECTO = "http://localhost:11434"

GLOSARIO_DEFECTO = [
    "machine learning",
    "JSON",
    "prompt",
    "pipeline",
    "benchmark",
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
    ruta_base = RAIZ_REPO / "data" / "fixtures"

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


# ---------------------------------------------------------------------------
# Configuración del entorno, claves y modelos en caché
# ---------------------------------------------------------------------------


def cargar_variables_entorno() -> None:
    """B2: lee el archivo .env de la raíz del repo, si existe, sin pisar variables ya definidas."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - python-dotenv figura en requirements.txt
        return
    load_dotenv(RAIZ_REPO / ".env")


def obtener_api_key_gemini() -> str | None:
    """Devuelve GEMINI_API_KEY desde el entorno (.env incluido) o desde los secrets de Streamlit."""
    clave = (os.getenv("GEMINI_API_KEY") or "").strip()
    if clave:
        return clave
    try:
        # load_if_toml_exists() evita el st.error que Streamlit muestra si no hay secrets.toml.
        if not st.secrets.load_if_toml_exists():
            return None
        clave = str(st.secrets.get("GEMINI_API_KEY") or "").strip()
    except Exception:
        return None
    return clave or None


def detector_disponible() -> bool:
    """Indica si el detector mmBERT puede cargarse (requiere transformers, que no se despliega)."""
    return importlib.util.find_spec("transformers") is not None


@st.cache_resource(show_spinner="Cargando el modelo de transcripción (solo la primera vez)…")
def obtener_modelo_whisper(modelo: str) -> Any:
    """B8: carga el modelo Whisper una sola vez por proceso y lo reutiliza entre sesiones."""
    return cargar_modelo_whisper(modelo)


@st.cache_resource(show_spinner=False)
def obtener_detector() -> DetectorSegmentos:
    """Carga el detector mmBERT (en desarrollo) una sola vez por proceso."""
    return DetectorSegmentos()


def firma_entrada(fuente_audio: Any, plantilla: str) -> tuple[Any, ...]:
    """Identifica la entrada actual (archivo subido y plantilla) para detectar cambios."""
    if fuente_audio is None:
        return (None, plantilla)
    return (
        getattr(fuente_audio, "file_id", None),
        getattr(fuente_audio, "name", None),
        getattr(fuente_audio, "size", None),
        plantilla,
    )


def descartar_resultado_si_cambio_la_entrada(fuente_audio: Any, plantilla: str) -> None:
    """B9: borra el resultado anterior cuando cambian el archivo subido o la plantilla."""
    firma = firma_entrada(fuente_audio, plantilla)
    if st.session_state.get("firma_entrada") == firma:
        return
    habia_resultado = "resultado_procesado" in st.session_state
    st.session_state.pop("resultado_procesado", None)
    st.session_state.pop("transcripcion_procesada", None)
    if habia_resultado:
        st.session_state["reproductor_inicio_s"] = 0.0
    st.session_state["firma_entrada"] = firma


# ---------------------------------------------------------------------------
# Procesamiento del audio
# ---------------------------------------------------------------------------


def _transcribir_archivo_temporal(fuente_audio: Any, modelo_whisper: str, glosario: list[str]) -> Transcripcion:
    """Transcribe el audio desde un archivo temporal que se borra siempre (no se guarda audio)."""
    nombre_archivo = getattr(fuente_audio, "name", "audio.m4a")
    sufijo = Path(nombre_archivo).suffix or ".m4a"
    ruta_tmp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as tmp_file:
            ruta_tmp = tmp_file.name
            tmp_file.write(fuente_audio.getvalue())
        return transcribir_audio(
            ruta_tmp,
            modelo=modelo_whisper,
            glosario_adicional=glosario,
            modelo_cargado=obtener_modelo_whisper(modelo_whisper),
        )
    finally:
        if ruta_tmp and os.path.exists(ruta_tmp):
            try:
                os.unlink(ruta_tmp)
            except OSError:
                pass


class OllamaNoDisponible(Exception):
    """Ollama no responde: solo existe cuando la app se ejecuta en local."""


_PATRONES_SENSIBLES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"https?://\S+", re.IGNORECASE), "[dirección oculta]"),
    (re.compile(r"HTTPS?ConnectionPool\([^)]*\)", re.IGNORECASE), "conexión"),
    (re.compile(r"\burl:\s*\S+", re.IGNORECASE), "url: [oculta]"),
    (re.compile(r"[\w.-]*googleapis\.com\S*", re.IGNORECASE), "[servicio de IA]"),
    (re.compile(r"\b(key|api[_-]?key|x-goog-api-key)\s*[=:]\s*[^\s&,;]+", re.IGNORECASE), r"\1=[oculta]"),
]


def ocultar_datos_sensibles(texto: str, secretos: list[str | None] | None = None) -> str:
    """Quita del texto las claves conocidas, las URL y los hosts de la API antes de mostrarlo."""
    limpio = texto
    for secreto in secretos or []:
        if secreto:
            limpio = limpio.replace(secreto, "[clave oculta]")
    for patron, reemplazo in _PATRONES_SENSIBLES:
        limpio = patron.sub(reemplazo, limpio)
    limpio = " ".join(limpio.split())
    return limpio[:300] + ("…" if len(limpio) > 300 else "")


def _cadena_de_causas(exc: BaseException) -> list[BaseException]:
    cadena: list[BaseException] = []
    actual: BaseException | None = exc
    while actual is not None and actual not in cadena:
        cadena.append(actual)
        actual = actual.__cause__ or actual.__context__
    return cadena


def en_streamlit_cloud() -> bool:
    """T69: detecta si la app corre en Streamlit Community Cloud."""
    return bool(
        os.getenv("STREAMLIT_SHARING_MODE")
        or os.getenv("IS_STREAMLIT_CLOUD")
        or os.getenv("STREAMLIT_COMMUNITY_CLOUD")
        or os.path.exists("/app")
        or (os.getenv("HOME") == "/home/appuser")
    )


def _formatear_proveedor(proveedor: str) -> str:
    """T69: en Streamlit Cloud la opción Ollama indica 'solo en tu laptop'."""
    if proveedor == PROVEEDOR_OLLAMA and en_streamlit_cloud():
        return f"{proveedor} (solo en tu laptop)"
    return proveedor


def mensaje_error_amigable(
    exc: BaseException,
    etapa: str,
    usar_ollama: bool,
    secretos: list[str | None] | None = None,
) -> str:
    """B4 / T69: traduce una excepción a un mensaje en español, con la causa y sin URL ni claves."""
    causas = _cadena_de_causas(exc)
    sin_conexion = any(isinstance(c, requests.ConnectionError) for c in causas)
    if isinstance(exc, OllamaNoDisponible) or (usar_ollama and sin_conexion):
        return (
            "No se pudo conectar con Ollama. Para encenderlo, ejecuta 'ollama serve' en tu terminal y asegúrate "
            "de tener el modelo descargado con 'ollama run qwen3:4b'. "
            "Ollama solo está disponible cuando ejecutas la app en local (en tu laptop). "
            "En la versión publicada (Streamlit Cloud), elige Gemini o activa el modo demo."
        )

    if any(isinstance(c, requests.Timeout) for c in causas):
        causa = "el servicio tardó demasiado en responder"
    elif sin_conexion:
        causa = "no hay conexión con el servicio"
    else:
        causa = ocultar_datos_sensibles(str(exc) or type(exc).__name__, secretos)

    if etapa == "transcripcion":
        return (
            f"No se pudo transcribir el audio. Causa: {causa}. "
            "Prueba con otro archivo (m4a, mp3 o wav) o con el modelo Whisper `base`."
        )
    nombre_proveedor = "Ollama" if usar_ollama else "Gemini"
    return (
        f"No se pudo estructurar la transcripción con {nombre_proveedor}. Causa: {causa}. "
        "Vuelve a intentarlo en unos minutos; si el problema sigue, activa el modo demo."
    )


def ollama_responde(host: str, timeout_s: float = 3.0) -> bool:
    """Comprueba con una consulta corta que el servidor de Ollama esté en marcha."""
    try:
        requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout_s)
    except requests.RequestException:
        return False
    return True


def procesar_audio(
    fuente_audio: Any,
    clave_plantilla: str,
    glosario: list[str],
    modelo_whisper: str,
    usar_ollama: bool,
    api_key: str | None,
    modo_analisis: str,
) -> tuple[Any, Transcripcion] | None:
    """Transcribe y estructura el audio subido. Devuelve (resultado, transcripción) o None si falla.

    Los errores se muestran con st.error en español (sin traceback, URL ni clave) y el
    estado del proceso queda marcado como error.
    """
    usa_detector = modo_analisis == "detector"
    total_pasos = 3 if usa_detector else 2
    nombre_proveedor = "Ollama" if usar_ollama else "Gemini"
    etapa = "transcripcion"
    mensaje_error: str | None = None
    resultado: Any = None
    transcripcion: Transcripcion | None = None

    with st.status("Procesando audio con Minuta…", expanded=True) as estado:
        try:
            if usar_ollama and not ollama_responde(os.getenv("OLLAMA_HOST") or OLLAMA_HOST_DEFECTO):
                raise OllamaNoDisponible()

            st.write(f"🎙️ Paso 1 de {total_pasos}: transcribiendo el audio con faster-whisper…")
            transcripcion = _transcribir_archivo_temporal(fuente_audio, modelo_whisper, glosario)

            etapa = "estructuracion"
            detector = None
            if usa_detector:
                # B6: este texto solo aparece cuando el detector se usa.
                st.write("🧠 Paso 2 de 3: clasificando segmentos con el detector mmBERT (en desarrollo)…")
                detector = obtener_detector()

            st.write(
                f"✨ Paso {total_pasos} de {total_pasos}: estructurando notas, mapa y tareas con {nombre_proveedor}…"
            )
            tipo_plantilla: TipoPlantilla = clave_plantilla  # type: ignore[assignment]
            proveedor: ProveedorLLM = ProveedorOllama() if usar_ollama else ProveedorGemini(api_key=api_key)
            resultado = estructurar_transcripcion(
                transcripcion=transcripcion,
                tipo_plantilla=tipo_plantilla,
                proveedor=proveedor,
                modo=modo_analisis,  # type: ignore[arg-type]
                detector=detector,
            )
        except Exception as exc:  # noqa: BLE001 - todo error se muestra como mensaje amigable
            mensaje_error = mensaje_error_amigable(exc, etapa, usar_ollama, secretos=[api_key])
            logger.warning(
                "Fallo al procesar el audio (%s, %s): %s",
                etapa,
                type(exc).__name__,
                ocultar_datos_sensibles(str(exc), [api_key]),
            )
            estado.update(label="No se pudo procesar el audio", state="error", expanded=True)
        else:
            estado.update(label="¡Procesamiento completado!", state="complete", expanded=False)

    if mensaje_error is not None or transcripcion is None:
        st.error(mensaje_error or "No se pudo procesar el audio.")
        return None
    return resultado, transcripcion


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------


def _inyectar_estilos() -> None:
    """Inyecta la identidad visual de marca de Minuta (T80).

    Inspirada en el promo phonk (scene-app.html, scene-drop.html):
    - Fondo oscuro #0B0B0F, acento lima #C6FF3D, superficies #181824 / #1E293B.
    - Tipografías: Archivo Black (titulares), JetBrains Mono (badges, marcas), Inter (cuerpo).
    - Botones de píldora (9999px) y tarjetas con radio 18px-24px.
    """
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Inter:ital,wght@0,400;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;600;700&display=swap');

        /* Contenedor principal Mobile-First */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 720px;
        }

        /* Tipografías base */
        html, body, [class*="css"], .stMarkdown, p, div {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #F8FAFC;
        }

        h1, h2, h3, [data-testid="stHeadingWithActionElements"] {
            font-family: 'Archivo Black', -apple-system, BlinkMacSystemFont, sans-serif !important;
            letter-spacing: -0.02em !important;
            color: #FFFFFF !important;
        }

        /* Ocultar título genérico de Streamlit para lucir el encabezado de marca */
        .stTitle, [data-testid="stTitle"] {
            display: none !important;
        }
        [data-testid="stTitle"] + [data-testid="stCaptionContainer"] {
            display: none !important;
        }

        /* Encabezado de marca Minuta */
        .minuta-header-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            margin-bottom: 1.8rem;
            padding: 10px 0;
        }

        .minuta-logo-lockup {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 4px;
        }

        .minuta-mic-svg {
            width: 38px;
            height: 38px;
            flex-shrink: 0;
        }

        .minuta-logo-text {
            font-family: 'Archivo Black', sans-serif;
            font-size: 2.6rem;
            line-height: 1;
            color: #FFFFFF;
            letter-spacing: -0.04em;
        }

        .minuta-logo-dot {
            color: #C6FF3D;
        }

        .minuta-slogan {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.95rem;
            color: #94A3B8;
            margin-top: 6px;
            margin-bottom: 16px;
            letter-spacing: -0.01em;
        }

        /* Píldoras de pasos */
        .minuta-steps-row {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
            width: 100%;
            margin-top: 4px;
        }

        .minuta-step-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 9999px;
            background: #1E293B;
            color: #F8FAFC;
            border: 1px solid #334155;
            white-space: nowrap;
        }

        .minuta-step-pill.highlight {
            background: #C6FF3D;
            color: #0B0B0F;
            border: 1px solid #C6FF3D;
            font-weight: 700;
        }

        /* Botones estilo píldora (mínimo 44px de alto táctil) */
        .stButton > button {
            width: 100%;
            min-height: 46px;
            border-radius: 9999px !important;
            font-family: 'Inter', sans-serif;
            font-size: 15px;
            font-weight: 700;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        /* Botón primario de acción (Procesar) */
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"] {
            background-color: #C6FF3D !important;
            color: #0B0B0F !important;
            border: none !important;
            font-family: 'Inter', sans-serif !important;
            font-weight: 700 !important;
            font-size: 16px !important;
        }
        .stButton > button[kind="primary"]:hover,
        .stButton > button[data-testid="baseButton-primary"]:hover {
            background-color: #D4FF66 !important;
            color: #0B0B0F !important;
            transform: scale(1.01);
            box-shadow: 0 0 20px rgba(198, 255, 61, 0.4);
        }

        /* Botones secundarios (como ▶ [mm:ss]) */
        .stButton > button[kind="secondary"],
        .stButton > button[data-testid="baseButton-secondary"] {
            background-color: #181824 !important;
            color: #C6FF3D !important;
            border: 1.5px solid #C6FF3D !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-weight: 700 !important;
            font-size: 13.5px !important;
        }
        .stButton > button[kind="secondary"]:hover,
        .stButton > button[data-testid="baseButton-secondary"]:hover {
            background-color: #C6FF3D !important;
            color: #0B0B0F !important;
            border-color: #C6FF3D !important;
            transform: scale(1.02);
            box-shadow: 0 0 15px rgba(198, 255, 61, 0.35);
        }

        /* Zona de subida de archivos (borde punteado lima) */
        [data-testid="stFileUploader"] {
            background-color: #181824 !important;
            border: 2px dashed #C6FF3D !important;
            border-radius: 20px !important;
            padding: 16px !important;
            margin-bottom: 12px !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4) !important;
        }
        [data-testid="stFileUploader"] section {
            background-color: transparent !important;
            padding: 8px !important;
        }
        [data-testid="stFileUploader"] small {
            color: #94A3B8 !important;
            font-family: 'Inter', sans-serif;
        }

        /* Tarjetas de contenido oscuro */
        .minuta-card {
            background-color: #181824;
            border: 1px solid #2D2D3D;
            border-radius: 20px;
            padding: 18px 20px;
            margin-bottom: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        }

        /* Badges de minuto y etiquetas */
        .minuta-badge {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 12px;
            color: #C6FF3D;
            background-color: rgba(198, 255, 61, 0.12);
            border: 1px solid rgba(198, 255, 61, 0.35);
            border-radius: 6px;
            padding: 2px 7px;
            margin-right: 6px;
            letter-spacing: 0.02em;
        }

        /* Badge EN para Términos en inglés */
        .minuta-badge-en {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 800;
            font-size: 11px;
            color: #0B0B0F;
            background-color: #C6FF3D;
            border-radius: 9999px;
            padding: 2px 8px;
            margin-right: 6px;
            vertical-align: middle;
            letter-spacing: 0.05em;
        }

        .minuta-badge-sec {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            padding: 2px 7px;
            font-size: 11px;
            font-weight: 600;
            color: #CBD5E1;
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 6px;
            margin-right: 6px;
        }

        /* Cita con borde izquierdo lima */
        .minuta-quote {
            border-left: 3px solid #C6FF3D;
            padding-left: 14px;
            margin-top: 8px;
            font-family: 'Inter', sans-serif;
            font-style: italic;
            color: #CBD5E1;
            font-size: 14px;
            line-height: 1.45;
        }

        /* Marco blanco redondeado para el mapa mental */
        .minuta-map-frame {
            background-color: #FFFFFF;
            border-radius: 24px;
            padding: 16px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.7), 0 0 30px rgba(198, 255, 61, 0.15);
            margin-bottom: 18px;
            overflow: hidden;
        }

        /* Pestañas estilizadas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            display: flex;
            flex-wrap: wrap;
            border-bottom: 1px solid #2D2D3D;
            padding-bottom: 4px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            font-weight: 600;
            color: #94A3B8;
            border-radius: 8px 8px 0 0;
            background: transparent;
        }
        .stTabs [aria-selected="true"] {
            color: #C6FF3D !important;
            font-weight: 700 !important;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: #C6FF3D !important;
            height: 3px !important;
        }

        /* Expander discreto */
        [data-testid="stExpander"] {
            background-color: #14141E !important;
            border: 1px solid #2D2D3D !important;
            border-radius: 16px !important;
            margin-top: 10px;
            margin-bottom: 16px;
        }

        /* Estilo para los selectbox y text areas */
        [data-baseweb="select"] > div,
        .stTextArea textarea {
            background-color: #181824 !important;
            border-color: #334155 !important;
            color: #F8FAFC !important;
            border-radius: 12px !important;
        }

        /* Audio player styling */
        audio {
            border-radius: 9999px;
            width: 100%;
            margin-top: 8px;
            margin-bottom: 6px;
        }

        /* Alertas estilizadas en modo oscuro */
        div[data-testid="stAlert"] {
            background-color: #181824 !important;
            border: 1px solid #2D2D3D !important;
            border-left: 4px solid #C6FF3D !important;
            border-radius: 16px !important;
        }
        div[data-testid="stAlert"] p, div[data-testid="stAlert"] span {
            color: #F8FAFC !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Alias para retrocompatibilidad con tests existentes
aplicar_estilos_movil = _inyectar_estilos


def _slug_de_resultado(resultado: Any) -> str:
    if isinstance(resultado, ResultadoPonencia):
        return "ponencia"
    if isinstance(resultado, ResultadoReunion):
        return "reunion"
    return "entrevista"


def _renderizar_terminos_ingles(terminos: list[Any], prefijo: str) -> None:
    """Renderiza la sección de términos en inglés con botón ▶ [mm:ss] y transcripción original."""
    st.markdown("### 🇬🇧 Términos en inglés")
    if not terminos:
        st.info("No se detectaron términos en inglés en este audio.")
        return
    for i_term, t in enumerate(terminos):
        tag = segundos_a_tiempo(t.evidencia.inicio_s)
        col_t, col_c = st.columns([1, 4])
        with col_t:
            if st.button(f"▶ {tag}", key=f"btn_term_{prefijo}_{i_term}"):
                st.session_state["reproductor_inicio_s"] = t.evidencia.inicio_s
                st.rerun()
        with col_c:
            trans_extra = ""
            if t.transcrito.strip().lower() != t.termino.strip().lower():
                trans_extra = f' <span style="color: #6c757d; font-size: 0.9em;">(se transcribió «{html.escape(t.transcrito)}»)</span>'
            st.markdown(
                f"""
                <div class="minuta-card">
                  <span class="minuta-badge-en">EN</span><strong>• {html.escape(t.termino)}</strong>{trans_extra}<br>
                  <div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(t.evidencia.cita)}"</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def renderizar_resultado(resultado: Any, transcripcion: Transcripcion | None, fuente_audio: Any = None) -> None:
    """Muestra el reproductor, las pestañas de la plantilla y la sección de exportación.

    B7: las claves de los botones se arman con posiciones (enumerate), nunca con ids de nodo
    ni con prefijos de citas, porque el LLM puede repetirlos. B10: todo texto del modelo que
    entra en HTML crudo pasa por html.escape.
    """
    clave_slug = _slug_de_resultado(resultado)

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
            for i_idea, idea in enumerate(resultado.ideas_clave):
                st.markdown(f"**• {idea.titulo}**")
                st.write(idea.resumen)
                for i_ev, ev in enumerate(idea.evidencias):
                    tag = segundos_a_tiempo(ev.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_idea_{i_idea}_{i_ev}"):
                            st.session_state["reproductor_inicio_s"] = ev.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f'<div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(ev.cita)}"</div>',
                            unsafe_allow_html=True,
                        )

            st.markdown("### ❓ Preguntas del Público y Pendientes")
            if resultado.preguntas:
                for i_preg, p in enumerate(resultado.preguntas):
                    tag = segundos_a_tiempo(p.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_preg_{i_preg}"):
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

            _renderizar_terminos_ingles(getattr(resultado, "terminos_ingles", []), "ponencia")

        with pestana_mapa:
            st.markdown(f"**Árbol temático interactivo:** *{resultado.mapa.titulo}*")
            st.markdown('<div class="minuta-map-frame">', unsafe_allow_html=True)
            html_mapa = generar_html_markmap(resultado.mapa.to_markdown(), altura_px=460)
            components.html(html_mapa, height=480, scrolling=False)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("#### Nodos del mapa con marca temporal y cita literal")
            nodos_tiempo = extraer_nodos_con_tiempo(resultado.mapa.raiz)

            for i_nodo, nodo in enumerate(nodos_tiempo):
                col_tiempo, col_titulo = st.columns([1, 3])
                with col_tiempo:
                    boton_label = f"▶ {nodo['tiempo_tag']}"
                    if st.button(boton_label, key=f"btn_nodo_{i_nodo}"):
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
            for i_tema, tema in enumerate(resultado.temas):
                st.markdown(f"**• {tema.titulo}**")
                st.write(tema.resumen)
                for i_ev, ev in enumerate(tema.evidencias):
                    tag = segundos_a_tiempo(ev.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_tema_{i_tema}_{i_ev}"):
                            st.session_state["reproductor_inicio_s"] = ev.inicio_s
                            st.rerun()
                    with col_c:
                        st.markdown(
                            f'<div class="minuta-quote"><span class="minuta-badge">{tag}</span>"{html.escape(ev.cita)}"</div>',
                            unsafe_allow_html=True,
                        )

            st.markdown("### 🤝 Acuerdos")
            if resultado.acuerdos:
                for i_acuerdo, a in enumerate(resultado.acuerdos):
                    tag = segundos_a_tiempo(a.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_acuerdo_{i_acuerdo}"):
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
                for i_tarea, t in enumerate(resultado.tareas):
                    resp = f" — Responsable: **{html.escape(t.responsable)}**" if t.responsable else ""
                    limite = f" (Límite: {html.escape(t.fecha_limite)})" if t.fecha_limite else ""
                    tag = segundos_a_tiempo(t.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_tarea_{i_tarea}"):
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
                for i_pend, p in enumerate(resultado.pendientes):
                    tag = segundos_a_tiempo(p.evidencia.inicio_s)
                    col_t, col_c = st.columns([1, 4])
                    with col_t:
                        if st.button(f"▶ {tag}", key=f"btn_pend_{i_pend}"):
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

            _renderizar_terminos_ingles(getattr(resultado, "terminos_ingles", []), "reunion")

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
            for i_nodo, nodo in enumerate(nodos_tiempo):
                col_tiempo, col_titulo = st.columns([1, 3])
                with col_tiempo:
                    boton_label = f"▶ {nodo['tiempo_tag']}"
                    if st.button(boton_label, key=f"btn_esq_{i_nodo}"):
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

            st.markdown("### 📚 Códigos temáticos")
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
            for i_frag, f in enumerate(resultado.fragmentos):
                tag = segundos_a_tiempo(f.evidencia.inicio_s)
                col_t, col_c = st.columns([1, 4])
                with col_t:
                    if st.button(f"▶ {tag}", key=f"btn_frag_{i_frag}"):
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

            _renderizar_terminos_ingles(getattr(resultado, "terminos_ingles", []), "entrevista")

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


def _renderizar_encabezado_marca() -> None:
    """Renderiza el logotipo y encabezado de marca de Minuta (T80)."""
    st.markdown(
        """
        <div class="minuta-header-box">
          <div class="minuta-logo-lockup">
            <svg class="minuta-mic-svg" viewBox="0 0 24 24" fill="none" stroke="#C6FF3D" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
            <span class="minuta-logo-text">MINUTA<span class="minuta-logo-dot">.</span></span>
          </div>
          <div class="minuta-slogan">Graba. Sube. Vuelve al minuto exacto.</div>
          <div class="minuta-steps-row">
            <span class="minuta-step-pill">1. Graba con tu celular</span>
            <span class="minuta-step-pill">2. Sube el archivo</span>
            <span class="minuta-step-pill highlight">3. Al minuto exacto</span>
          </div>
        </div>
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

    cargar_variables_entorno()
    aplicar_estilos_movil()

    # Inicialización de estado en sesión
    if "reproductor_inicio_s" not in st.session_state:
        st.session_state["reproductor_inicio_s"] = 0.0
    if "glosario_usuario" not in st.session_state:
        st.session_state["glosario_usuario"] = ", ".join(GLOSARIO_DEFECTO)

    # Encabezado principal
    st.title("🎙️ Minuta")
    st.caption("Tu alternativa económica a las grabadoras con IA (como Plaud) usando tu celular.")
    _renderizar_encabezado_marca()

    # B5: el modo demo arranca apagado y queda visible arriba, fuera del expander.
    modo_demo = st.toggle(
        "🧪 Modo demo: ver un ejemplo precalculado",
        value=False,
        help=(
            "Muestra notas ya generadas a partir de una transcripción de ejemplo (data/fixtures/). "
            "No procesa audio ni llama a ningún modelo de IA."
        ),
    )

    # 1. Guía de grabación visible
    st.info(
        "📱 **Guía de grabación con celular:**\n\n"
        "Graba con la grabadora de voz nativa del celular (preferentemente en **modo avión** "
        "para charlas largas) y sube el archivo aquí."
    )

    # 2. Paso 1 a la vista: "¿Qué grabaste?" (T68)
    plantilla = st.selectbox(
        "¿Qué grabaste?",
        options=PLANTILLAS_DISPONIBLES,
        index=0,
        help="Selecciona el formato adecuado según la naturaleza del audio.",
    )

    # 3. Paso 2 a la vista: "Sube tu audio" (T68)
    st.subheader("1. Audio de la sesión")

    # Opción condicional si la versión de streamlit soporta st.audio_input
    if hasattr(st, "audio_input"):
        st.write("Graba un audio directo:")
        audio_grabado = getattr(st, "audio_input")("Grabar audio con el micrófono")
    else:
        audio_grabado = None

    archivo_audio = st.file_uploader(
        "Sube tu audio (grabado con el celular):",
        type=["m4a", "mp3", "wav"],
        help="Formatos soportados: m4a, mp3, wav. Máximo 200 MB.",
    )

    fuente_audio = archivo_audio or audio_grabado
    descartar_resultado_si_cambio_la_entrada(fuente_audio, plantilla)

    # 4. Opciones avanzadas en un bloque plegable cerrado por defecto (T68)
    detector_listo = detector_disponible()
    with st.expander("⚙️ Opciones avanzadas", expanded=False):
        proveedor_seleccionado = st.selectbox(
            "Proveedor de IA para estructuración:",
            options=[PROVEEDOR_GEMINI, PROVEEDOR_OLLAMA],
            index=0,
            format_func=_formatear_proveedor,
            help="Gemini funciona en la versión publicada. Ollama solo funciona si ejecutas la app en local.",
        )
        modelo_whisper = st.selectbox(
            "Modelo de transcripción Whisper:",
            options=["small", "base"],
            index=0,
            help="small para mayor fidelidad acústica en laptop; base para bajo consumo de memoria.",
        )
        # B6: "Solo LLM" por defecto; el detector está en desarrollo y se deshabilita si no puede cargarse.
        modo_analisis = st.radio(
            "Modo de análisis:",
            options=list(ETIQUETAS_MODO_ANALISIS),
            index=0,
            format_func=lambda m: ETIQUETAS_MODO_ANALISIS[m],
            disabled=not detector_listo,
            help=(
                "El detector está en desarrollo: prioriza tareas y filtra el relleno antes de consultar al LLM."
                if detector_listo
                else "El detector está en desarrollo y no está disponible en esta versión: el análisis usa solo el LLM."
            ),
        )
        if not detector_listo:
            modo_analisis = "solo_llm"

        glosario_texto = st.text_area(
            "Términos en inglés que esperas escuchar (opcional):",
            value=st.session_state["glosario_usuario"],
            help="Pista opcional de términos en inglés esperados para ayudar a detectarlos en la transcripción.",
            height=75,
        )
        st.session_state["glosario_usuario"] = glosario_texto

    clave_slug = SLUG_POR_PLANTILLA[plantilla]
    usar_ollama = proveedor_seleccionado == PROVEEDOR_OLLAMA

    # 5. Procesamiento o carga de datos
    resultado: Any = None
    transcripcion: Transcripcion | None = None

    if modo_demo:
        st.success(
            f"⚡ Modo demo activo: se muestra un ejemplo precalculado de **{plantilla}**. "
            "No se procesa audio ni se llama a ningún modelo."
        )
        try:
            resultado, transcripcion = cargar_fixture_demo(plantilla)
        except Exception as err:
            st.error(f"No se pudo cargar el ejemplo precalculado: {err}")
            return
    else:
        api_key: str | None = None
        if not usar_ollama:
            api_key = obtener_api_key_gemini()
            if not api_key:
                st.error(
                    "Falta la clave de Gemini (GEMINI_API_KEY). Defínela en el archivo `.env` si ejecutas "
                    "la app en local, o en los *Secrets* de Streamlit Community Cloud, y vuelve a cargar la página. "
                    "Mientras tanto, puedes activar el modo demo para ver un ejemplo precalculado."
                )
                st.stop()

        if fuente_audio is None:
            st.warning("Sube un archivo de audio para procesarlo, o activa el modo demo para ver un ejemplo precalculado.")
            return

        if st.button("🚀 Procesar audio con Minuta", type="primary"):
            glosario_lista = [t.strip() for t in glosario_texto.split(",") if t.strip()]
            salida = procesar_audio(
                fuente_audio,
                clave_plantilla=clave_slug,
                glosario=glosario_lista,
                modelo_whisper=modelo_whisper,
                usar_ollama=usar_ollama,
                api_key=api_key,
                modo_analisis=modo_analisis,
            )
            if salida is None:
                return
            st.session_state["resultado_procesado"], st.session_state["transcripcion_procesada"] = salida

        if "resultado_procesado" not in st.session_state:
            st.info("Presiona **🚀 Procesar audio con Minuta** para transcribir y estructurar el audio.")
            return
        resultado = st.session_state["resultado_procesado"]
        transcripcion = st.session_state.get("transcripcion_procesada")

    if resultado is None:
        return

    renderizar_resultado(resultado, transcripcion, fuente_audio)


if __name__ == "__main__":
    main()
