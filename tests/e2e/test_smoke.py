"""Pruebas de humo de extremo a extremo (E2E) para la aplicación Minuta Streamlit.

Verifica con Streamlit AppTest:
- Inicialización sin excepciones (el modo demo arranca apagado, L51 B5).
- Las 3 plantillas en modo demo y la sección de exportación.
- Interacción con la interfaz y cambio entre plantillas.
- Interacción con los botones de marca temporal del reproductor.
- Conmutación del modo demo.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RUTA_APP = str(ROOT_DIR / "app" / "streamlit_app.py")


def _app_en_demo() -> AppTest:
    """Arranca la app y activa el modo demo (que arranca apagado desde L51 B5)."""
    at = AppTest.from_file(RUTA_APP)
    at.run()
    assert not at.exception, f"Excepción al iniciar aplicación: {at.exception}"
    at.toggle[0].set_value(True).run()
    assert not at.exception, f"Excepción al activar el modo demo: {at.exception}"
    return at


def test_smoke_inicio_app_modo_demo() -> None:
    """Verifica que la aplicación inicie correctamente, con el modo demo apagado por defecto."""
    at = AppTest.from_file(RUTA_APP)
    at.run()

    assert not at.exception, f"Excepción al iniciar aplicación: {at.exception}"
    assert any("MINUTA" in m.value for m in at.markdown)  # encabezado de marca
    assert len(at.info) > 0
    assert "Guía de grabación" in at.info[0].value

    # Verificar que la plantilla por defecto sea Ponencia
    assert len(at.selectbox) > 0
    assert at.selectbox[0].value == "Ponencia / Clase / Charla"

    # Verificar que el modo demo esté apagado por defecto (L51 B5)
    assert len(at.toggle) > 0
    assert at.toggle[0].value is False


def test_smoke_cambio_plantilla_reunion() -> None:
    """Verifica el cambio a la plantilla 'Reunión' y renderizado de sus pestañas."""
    at = _app_en_demo()

    # Cambiar a plantilla Reunión
    at.selectbox[0].select("Reunión").run()

    assert not at.exception, f"Excepción al cambiar a Reunión: {at.exception}"
    assert at.selectbox[0].value == "Reunión"

    # Cambiar de regreso a Ponencia
    at.selectbox[0].select("Ponencia / Clase / Charla").run()
    assert not at.exception
    assert at.selectbox[0].value == "Ponencia / Clase / Charla"


def test_smoke_interaccion_reproductor_nodo() -> None:
    """Verifica que hacer clic en una marca de tiempo actualice la sesión sin excepciones."""
    at = _app_en_demo()

    # Localizar botones de salto temporal
    botones_tiempo = [b for b in at.button if "▶" in (b.label or "")]
    assert len(botones_tiempo) > 0, "Debe existir al menos un botón de marca temporal en modo demo"

    # Pulsar el primer botón temporal
    botones_tiempo[0].click().run()
    assert not at.exception, f"Excepción tras pulsar botón temporal: {at.exception}"
    assert at.session_state["reproductor_inicio_s"] >= 0.0


def test_smoke_toggle_modo_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que desactivar y reactivar el modo demo no lance excepciones no controladas."""
    # Con una clave falsa (sin llamadas a la API) el flujo real pide el audio.
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa-de-prueba")
    at = _app_en_demo()

    # Desactivar modo demo (sin audio debe mostrar advertencia sin caer)
    at.toggle[0].set_value(False).run()
    assert not at.exception
    assert len(at.warning) > 0

    # Reactivar modo demo
    at.toggle[0].set_value(True).run()
    assert not at.exception
    assert len(at.success) > 0


def test_smoke_cambio_plantilla_entrevista() -> None:
    """Verifica el cambio a la plantilla 'Entrevista'."""
    at = _app_en_demo()

    at.selectbox[0].select("Entrevista").run()
    assert not at.exception, f"Excepción en plantilla Entrevista: {at.exception}"
    assert at.selectbox[0].value == "Entrevista"


def test_smoke_botones_exportacion_disponibles() -> None:
    """Verifica que los botones de exportación se rendericen según la plantilla activa (L45)."""
    at = _app_en_demo()

    # En Ponencia (plantilla por defecto) se ofrecen 5 botones (incluye Mapa HTML y Transcripción)
    botones_descarga = at.get("download_button")
    assert len(botones_descarga) >= 4, f"Se esperaban al menos 4 botones de exportación, se hallaron {len(botones_descarga)}"
    download_labels = [b.label for b in botones_descarga]
    assert any("Markdown" in (lbl or "") for lbl in download_labels), "Falta botón de descarga Markdown"
    assert any("HTML" in (lbl or "") for lbl in download_labels), "Falta botón de descarga HTML en Ponencia"
    assert any("Word" in (lbl or "") for lbl in download_labels), "Falta botón de descarga Word"
    assert any("Excel" in (lbl or "") for lbl in download_labels), "Falta botón de descarga Excel"
    assert any("Transcripción" in (lbl or "") for lbl in download_labels), "Falta botón de descarga Transcripción"


def test_apptest_plantilla_clase_secciones_y_mapa() -> None:
    """Valida que la plantilla Clase / Ponencia muestre Notas de clase, Mapa mental y Transcripción (L45)."""
    at = _app_en_demo()

    # Verificar que el selectbox esté en Ponencia
    assert at.selectbox[0].value == "Ponencia / Clase / Charla"

    # Verificar presencia de secciones específicas de Clase
    markdown_texts = " ".join(m.value for m in at.markdown)
    assert "Ideas Clave" in markdown_texts
    assert "Árbol temático interactivo" in markdown_texts or "Mapa mental" in markdown_texts
    assert "Preguntas del Público" in markdown_texts or "Preguntas" in markdown_texts

    # Verificar que el botón de Mapa HTML está presente
    labels_descarga = [b.label for b in at.get("download_button")]
    assert any("HTML" in (lbl or "") for lbl in labels_descarga)


def test_apptest_plantilla_reunion_sin_mapa_mental() -> None:
    """Valida que la plantilla Reunión muestre Notas de reunión, To-dos, Acuerdos y NUNCA el mapa mental (L45)."""
    at = _app_en_demo()
    at.selectbox[0].select("Reunión").run()
    assert not at.exception

    markdown_texts = " ".join(m.value for m in at.markdown)
    # Secciones requeridas de reunión
    assert "Temas Tratados" in markdown_texts
    assert "Tareas (To-Do)" in markdown_texts or "To-Do" in markdown_texts
    assert "Acuerdos" in markdown_texts

    # Comprobar que NO aparece mapa mental ni markmap en Reunión (L45)
    assert "Árbol temático interactivo" not in markdown_texts
    labels_descarga = [b.label for b in at.get("download_button")]
    assert not any("HTML" in (lbl or "") for lbl in labels_descarga), "Reunión no debe ofrecer descarga de Mapa HTML"


def test_apptest_plantilla_entrevista_esquema_sin_markmap() -> None:
    """Valida que la plantilla Entrevista muestre Esquema por temas en lista y NO el diagrama markmap (L45)."""
    at = _app_en_demo()
    at.selectbox[0].select("Entrevista").run()
    assert not at.exception

    markdown_texts = " ".join(m.value for m in at.markdown)
    # Secciones requeridas de entrevista
    assert "Esquema Temático Jerárquico" in markdown_texts or "Esquema" in markdown_texts
    assert "Libro de Códigos" in markdown_texts or "Fragmentos Codificados" in markdown_texts

    # Comprobar que NO aparece el diagrama interactivo markmap (L45)
    assert "Árbol temático interactivo" not in markdown_texts
    labels_descarga = [b.label for b in at.get("download_button")]
    assert not any("HTML" in (lbl or "") for lbl in labels_descarga), "Entrevista no debe ofrecer descarga de Mapa HTML"


def test_modo_demo_tres_plantillas() -> None:
    """Verifica que el modo demo cargue y funcione sin excepciones en las 3 plantillas (L45)."""
    at = _app_en_demo()

    for plantilla in ["Ponencia / Clase / Charla", "Reunión", "Entrevista"]:
        at.selectbox[0].select(plantilla).run()
        assert not at.exception, f"Fallo al cargar modo demo en {plantilla}: {at.exception}"
        # Comprobar que se informa el modo demo activo
        success_texts = " ".join(s.value for s in at.success)
        assert "Modo demo activo" in success_texts
        # Debe haber botones de marca de tiempo [mm:ss] en todas las plantillas
        botones_tiempo = [b for b in at.button if "▶" in (b.label or "")]
        assert len(botones_tiempo) > 0, f"Debe haber botones de tiempo en demo para {plantilla}"


