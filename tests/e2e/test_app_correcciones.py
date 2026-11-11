"""Pruebas de las correcciones de la app (L51, Unidad B: B1-B10).

Usan Streamlit AppTest. Ninguna prueba llama a la API de Gemini ni guarda audio:
la transcripción y la estructuración se reemplazan con dobles de prueba.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parents[2]
RUTA_APP = str(ROOT_DIR / "app" / "streamlit_app.py")
TIEMPO_MAXIMO_S = 60


def _app() -> AppTest:
    at = AppTest.from_file(RUTA_APP, default_timeout=TIEMPO_MAXIMO_S)
    at.run()
    assert not at.exception, f"Excepción al iniciar: {at.exception}"
    return at


def _toggle_demo(at: AppTest):
    toggles = [t for t in at.toggle if "demo" in (t.label or "").lower()]
    assert toggles, "No se encontró el interruptor del modo demo"
    return toggles[0]


def _apagar_demo(at: AppTest) -> None:
    if _toggle_demo(at).value:
        _toggle_demo(at).set_value(False).run()


def _radio_modo(at: AppTest):
    radios = [r for r in at.radio if "Modo de análisis" in (r.label or "")]
    assert radios, "No se encontró el selector de modo de análisis"
    return radios[0]


# ---------------------------------------------------------------- B1 y B2: arranque


def test_b1_app_importa_minuta_sin_la_raiz_en_sys_path(tmp_path: Path) -> None:
    """`streamlit run app/streamlit_app.py` solo agrega app/ a sys.path: la app debe hallar minuta."""
    codigo = f"import runpy; runpy.run_path(r'{RUTA_APP}', run_name='arranque_minuta')"
    entorno = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    proceso = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=tmp_path,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert "ModuleNotFoundError" not in proceso.stderr, proceso.stderr[-2000:]
    assert proceso.returncode == 0, proceso.stderr[-2000:]


def test_b2_app_lee_el_archivo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """La app llama a load_dotenv() de python-dotenv al arrancar."""
    llamadas: list[tuple] = []
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: llamadas.append((a, k)) or False)
    _app()
    assert llamadas, "La app no llamó a load_dotenv()"


# ---------------------------------------------------------------- B3: sin clave


def test_b3_sin_clave_gemini_muestra_error_y_se_detiene() -> None:
    at = _app()
    _apagar_demo(at)
    assert not at.exception, f"Excepción sin clave: {at.exception}"

    errores = " ".join(e.value for e in at.error)
    assert "GEMINI_API_KEY" in errores, f"Se esperaba un error claro sin clave; errores: {errores!r}"
    avisos = " ".join(w.value for w in at.warning).lower()
    assert "offline" not in avisos
    assert not [b for b in at.button if "Procesar" in (b.label or "")], "Tras st.stop() no debe ofrecerse procesar"


def test_b3_con_clave_gemini_no_muestra_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con una clave definida (falsa, sin llamadas) el flujo real sigue y pide el audio."""
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa-de-prueba")
    at = _app()
    _apagar_demo(at)
    assert not at.exception
    assert not at.error, f"No debe haber errores con clave: {[e.value for e in at.error]}"
    assert at.warning, "Sin audio subido, la app debe pedir el archivo"


# ---------------------------------------------------------------- B5: modo demo


def test_b5_modo_demo_apagado_por_defecto_visible_y_explicado() -> None:
    at = _app()
    demo = _toggle_demo(at)
    assert demo.value is False, "El modo demo debe arrancar apagado"

    for expander in at.expander:
        assert not [t for t in expander.toggle if "demo" in (t.label or "").lower()], (
            "El interruptor del modo demo no debe estar dentro de un expander"
        )

    texto_demo = f"{demo.label} {demo.help or ''}".lower()
    assert "precalculado" in texto_demo, f"El interruptor debe avisar que es un ejemplo precalculado: {texto_demo!r}"

    demo.set_value(True).run()
    assert not at.exception
    exitos = " ".join(s.value for s in at.success).lower()
    assert "ejemplo precalculado" in exitos


# ---------------------------------------------------------------- B6: detector


def test_b6_modo_por_defecto_solo_llm_y_detector_en_desarrollo() -> None:
    at = _app()
    radio = _radio_modo(at)
    assert radio.value == "solo_llm"
    etiquetas_detector = [o for o in radio.options if "detector" in o.lower()]
    assert all("(en desarrollo)" in o for o in etiquetas_detector), radio.options
    if importlib.util.find_spec("transformers") is None:
        assert radio.disabled, "Sin el detector instalado la opción debe quedar deshabilitada"


# ---------------------------------------------------------------- B9: resultado anterior


def test_b9_cambiar_plantilla_borra_el_resultado_anterior(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa-de-prueba")
    at = _app()
    _apagar_demo(at)

    at.session_state["resultado_procesado"] = "resultado-anterior"
    at.session_state["transcripcion_procesada"] = "transcripcion-anterior"
    at.run()
    assert "resultado_procesado" in at.session_state, "Con la misma entrada el resultado se conserva"

    at.selectbox[0].select("Reunión").run()
    assert not at.exception
    assert "resultado_procesado" not in at.session_state
    assert "transcripcion_procesada" not in at.session_state


# ------------------------------------------- B4, B6, B7, B10: funciones de la app en AppTest
# AppTest.from_function escribe el cuerpo de la función en un archivo temporal: en Windows,
# un literal no ASCII ahí deja la corrida vacía y sin excepción. Los textos con tilde
# (por ejemplo "Reunión") se pasan por kwargs.


def _script_procesar(raiz: str, escenario: str, plantilla: str) -> None:
    import sys

    if raiz not in sys.path:
        sys.path.insert(0, raiz)

    from io import BytesIO
    from unittest.mock import MagicMock, patch

    import requests
    import streamlit as st

    import app.streamlit_app as appmod
    from minuta.proveedores import ErrorProveedorLLM

    class AudioFalso(BytesIO):
        name = "clip.m4a"

    resultado_fx, transcripcion_fx = appmod.cargar_fixture_demo(plantilla)
    url_api = "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=clave-secreta-123"

    transcribir = MagicMock(return_value=transcripcion_fx)
    estructurar = MagicMock(return_value=resultado_fx)
    sonda_ollama = MagicMock()
    usar_ollama = False
    if escenario == "fallo_transcripcion":
        transcribir.side_effect = RuntimeError(f"Fallo de red al descargar desde {url_api}")
    elif escenario == "fallo_gemini":
        estructurar.side_effect = ErrorProveedorLLM(f"Fallo en llamada a Gemini API: 400 Client Error for url: {url_api}")
    elif escenario == "ollama_inaccesible":
        usar_ollama = True
        sonda_ollama.side_effect = requests.ConnectionError(
            "HTTPConnectionPool(host='localhost', port=11434): Max retries exceeded with url: /api/tags"
        )

    with patch.object(appmod, "obtener_modelo_whisper", return_value=MagicMock()), patch.object(
        appmod, "transcribir_audio", transcribir
    ), patch.object(appmod, "estructurar_transcripcion", estructurar), patch.object(
        appmod, "ProveedorGemini", MagicMock()
    ), patch.object(appmod, "ProveedorOllama", MagicMock()), patch.object(appmod.requests, "get", sonda_ollama):
        salida = appmod.procesar_audio(
            AudioFalso(b"audio-de-prueba"),
            clave_plantilla="reunion",
            glosario=["journal"],
            modelo_whisper="base",
            usar_ollama=usar_ollama,
            api_key="clave-secreta-123",
            modo_analisis="solo_llm",
        )
    st.session_state["salida_ok"] = salida is not None


def _correr_procesar(escenario: str) -> AppTest:
    at = AppTest.from_function(
        _script_procesar,
        default_timeout=TIEMPO_MAXIMO_S,
        kwargs={"raiz": str(ROOT_DIR), "escenario": escenario, "plantilla": "Reunión"},
    )
    at.run()
    return at


def _textos_visibles(at: AppTest) -> str:
    partes = [e.value for e in at.error] + [m.value for m in at.markdown] + [s.label for s in at.status]
    return " ".join(partes)


@pytest.mark.parametrize("escenario", ["fallo_transcripcion", "fallo_gemini"])
def test_b4_error_amigable_sin_traceback_ni_url(escenario: str) -> None:
    at = _correr_procesar(escenario)
    assert not at.exception, f"El error no debe llegar como traceback: {at.exception}"
    assert at.error, "Se esperaba un st.error con la causa"
    assert at.status and at.status[0].state == "error"
    assert at.session_state["salida_ok"] is False

    visibles = _textos_visibles(at)
    assert "http" not in visibles.lower(), visibles
    assert "googleapis" not in visibles
    assert "clave-secreta-123" not in visibles
    assert "No se pudo" in at.error[0].value


def test_b4_ollama_inaccesible_explica_que_solo_funciona_en_local() -> None:
    at = _correr_procesar("ollama_inaccesible")
    assert not at.exception, f"{at.exception}"
    assert at.status and at.status[0].state == "error"
    mensaje = at.error[0].value
    assert "Ollama" in mensaje and "local" in mensaje, mensaje
    assert "http" not in _textos_visibles(at).lower()


def test_b4_b6_proceso_exitoso_sin_texto_de_mmbert_en_solo_llm() -> None:
    at = _correr_procesar("exito")
    assert not at.exception, f"{at.exception}"
    assert at.session_state["salida_ok"] is True
    assert at.status and at.status[0].state == "complete"
    assert not at.error
    assert "mmBERT" not in _textos_visibles(at), "Sin detector no se menciona mmBERT"


def _script_render_ids_repetidos(raiz: str, plantilla: str) -> None:
    import sys

    if raiz not in sys.path:
        sys.path.insert(0, raiz)

    import app.streamlit_app as appmod

    resultado, transcripcion = appmod.cargar_fixture_demo(plantilla)

    def _repetir_ids(nodo) -> None:
        nodo.id = "n1"
        for hijo in nodo.hijos:
            _repetir_ids(hijo)

    _repetir_ids(resultado.mapa.raiz)
    if hasattr(resultado, "ideas_clave"):
        resultado.ideas_clave = resultado.ideas_clave * 2
        resultado.preguntas = resultado.preguntas * 2
    if hasattr(resultado, "tareas"):
        resultado.temas = resultado.temas * 2
        resultado.acuerdos = resultado.acuerdos * 2
        resultado.tareas = resultado.tareas * 2
        resultado.pendientes = resultado.pendientes * 2
    if hasattr(resultado, "fragmentos"):
        resultado.fragmentos = resultado.fragmentos * 2

    appmod.renderizar_resultado(resultado, transcripcion)


@pytest.mark.parametrize("plantilla", ["Ponencia / Clase / Charla", "Reunión", "Entrevista"])
def test_b7_ids_repetidos_no_causan_duplicate_widget_id(plantilla: str) -> None:
    at = AppTest.from_function(
        _script_render_ids_repetidos,
        default_timeout=TIEMPO_MAXIMO_S,
        kwargs={"raiz": str(ROOT_DIR), "plantilla": plantilla},
    )
    at.run()
    assert not at.exception, f"Claves de widget repetidas en {plantilla}: {at.exception}"
    assert len([b for b in at.button if "▶" in (b.label or "")]) > 0


def _script_render_html_malicioso(raiz: str, plantilla: str) -> None:
    import sys

    if raiz not in sys.path:
        sys.path.insert(0, raiz)

    import app.streamlit_app as appmod

    resultado, transcripcion = appmod.cargar_fixture_demo(plantilla)
    resultado.tareas[0].responsable = "<img src=x onerror=alert(1)>"
    resultado.tareas[0].fecha_limite = "<script>alert(2)</script>"
    appmod.renderizar_resultado(resultado, transcripcion)


def test_b10_responsable_y_fecha_limite_se_escapan() -> None:
    at = AppTest.from_function(
        _script_render_html_malicioso,
        default_timeout=TIEMPO_MAXIMO_S,
        kwargs={"raiz": str(ROOT_DIR), "plantilla": "Reunión"},
    )
    at.run()
    assert not at.exception, f"{at.exception}"
    tarjetas = [m.value for m in at.markdown if "Responsable" in m.value]
    assert tarjetas, "No se renderizó la tarjeta de la tarea"
    html_tarjetas = " ".join(tarjetas)
    assert "<img src=x" not in html_tarjetas
    assert "<script>" not in html_tarjetas
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_tarjetas
    assert "&lt;script&gt;" in html_tarjetas
