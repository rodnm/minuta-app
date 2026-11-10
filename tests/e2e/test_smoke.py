"""Pruebas de humo de extremo a extremo (E2E) para la aplicación Minuta Streamlit.

Verifica con Streamlit AppTest:
- Inicialización sin excepciones en modo demo.
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


def test_smoke_inicio_app_modo_demo() -> None:
    """Verifica que la aplicación inicie correctamente en modo demo por defecto."""
    at = AppTest.from_file(RUTA_APP)
    at.run()

    assert not at.exception, f"Excepción al iniciar aplicación: {at.exception}"
    assert len(at.title) > 0
    assert "Minuta" in at.title[0].value
    assert len(at.info) > 0
    assert "Guía de grabación" in at.info[0].value

    # Verificar que la plantilla por defecto sea Ponencia
    assert len(at.selectbox) > 0
    assert at.selectbox[0].value == "Ponencia / Clase / Charla"

    # Verificar que el modo demo esté activo por defecto
    assert len(at.toggle) > 0
    assert at.toggle[0].value is True


def test_smoke_cambio_plantilla_reunion() -> None:
    """Verifica el cambio a la plantilla 'Reunión' y renderizado de sus pestañas."""
    at = AppTest.from_file(RUTA_APP)
    at.run()
    assert not at.exception

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
    at = AppTest.from_file(RUTA_APP)
    at.run()
    assert not at.exception

    # Localizar botones de salto temporal
    botones_tiempo = [b for b in at.button if "▶" in (b.label or "")]
    assert len(botones_tiempo) > 0, "Debe existir al menos un botón de marca temporal en modo demo"

    # Pulsar el primer botón temporal
    botones_tiempo[0].click().run()
    assert not at.exception, f"Excepción tras pulsar botón temporal: {at.exception}"
    assert at.session_state["reproductor_inicio_s"] >= 0.0


def test_smoke_toggle_modo_demo() -> None:
    """Verifica que desactivar y reactivar el modo demo no lance excepciones no controladas."""
    at = AppTest.from_file(RUTA_APP)
    at.run()
    assert not at.exception

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
    at = AppTest.from_file(RUTA_APP)
    at.run()
    assert not at.exception

    at.selectbox[0].select("Entrevista").run()
    assert not at.exception, f"Excepción en plantilla Entrevista: {at.exception}"
    assert at.selectbox[0].value == "Entrevista"
