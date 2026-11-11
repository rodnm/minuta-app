"""Pruebas E2E para Fase 3 (T68 y T69)."""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_t68_flujo_dos_pasos_y_opciones_avanzadas_en_expander():
    """T68: A la vista solo quedan '¿Qué grabaste?' y 'Sube tu audio'; los demás en 'Opciones avanzadas'."""
    at = AppTest.from_file(str(ROOT_DIR / "app" / "streamlit_app.py"), default_timeout=30)
    at.run()

    assert not at.exception, f"Error al iniciar app: {at.exception}"

    # 1. El interruptor del modo demo sigue visible arriba y fuera del expander
    assert len(at.toggle) > 0, "Debe existir el toggle de modo demo"
    demo_toggles = [t for t in at.toggle if "demo" in (t.label or "").lower()]
    assert demo_toggles, "Debe existir el toggle del modo demo"
    for exp in at.expander:
        assert not any("demo" in (t.label or "").lower() for t in exp.toggle), (
            "El modo demo no debe estar dentro del expander"
        )

    # 2. A la vista: "¿Qué grabaste?" y "Sube tu audio"
    # Selectbox de plantilla a la vista
    assert at.selectbox[0].label == "¿Qué grabaste?"
    # File uploader a la vista
    uploaders = [u for u in at.get("file_uploader") if "sube tu audio" in (u.label or "").lower()]
    assert uploaders, "El file uploader 'Sube tu audio' debe estar a la vista"

    # 3. Expander "Opciones avanzadas" cerrado (expanded=False)
    expanders_avanzados = [e for e in at.expander if "opciones avanzadas" in (e.label or "").lower()]
    assert expanders_avanzados, "Debe existir el expander 'Opciones avanzadas'"
    exp_avanzado = expanders_avanzados[0]
    assert exp_avanzado.proto.expanded is False, "El expander de opciones avanzadas debe arrancar cerrado"

    # Los controles avanzados están dentro del expander
    labels_expander = [s.label for s in exp_avanzado.selectbox]
    assert any("proveedor" in l.lower() for l in labels_expander), "El proveedor debe estar dentro del expander"
    assert any("whisper" in l.lower() for l in labels_expander), "El modelo Whisper debe estar dentro del expander"


def test_t68_tres_plantillas_en_modo_demo_sin_excepciones():
    """T68: Las 3 plantillas corren en modo demo sin excepciones."""
    at = AppTest.from_file(str(ROOT_DIR / "app" / "streamlit_app.py"), default_timeout=30)
    at.run()

    # Activar modo demo
    demo_toggle = [t for t in at.toggle if "demo" in (t.label or "").lower()][0]
    demo_toggle.set_value(True).run()

    for plantilla in ["Ponencia / Clase / Charla", "Reunión", "Entrevista"]:
        at.selectbox[0].select(plantilla).run()
        assert not at.exception, f"Excepción en modo demo con {plantilla}: {at.exception}"
        assert len(at.tabs) > 0, f"Debe mostrar pestañas de resultados en {plantilla}"


def test_t69_ollama_error_indica_como_encenderlo():
    """T69: Si Ollama no responde, el mensaje de error indica cómo encenderlo ('ollama serve')."""
    from app.streamlit_app import OllamaNoDisponible, mensaje_error_amigable

    msg = mensaje_error_amigable(OllamaNoDisponible(), etapa="estructuracion", usar_ollama=True)
    assert "ollama serve" in msg.lower(), f"El mensaje debe indicar cómo encender Ollama: {msg}"
    assert "solo" in msg.lower() and "laptop" in msg.lower()


def test_t69_opcion_ollama_en_streamlit_cloud(monkeypatch: pytest.MonkeyPatch):
    """T69: En Streamlit Cloud, la opción Ollama dice 'solo en tu laptop'."""
    monkeypatch.setenv("STREAMLIT_SHARING_MODE", "true")
    at = AppTest.from_file(str(ROOT_DIR / "app" / "streamlit_app.py"), default_timeout=30)
    at.run()

    expander_avanzado = [e for e in at.expander if "opciones avanzadas" in (e.label or "").lower()][0]
    prov_sb = [s for s in expander_avanzado.selectbox if "proveedor" in s.label.lower()][0]
    
    # La representación de opciones para Ollama debe indicar 'solo en tu laptop'
    from app.streamlit_app import _formatear_proveedor, PROVEEDOR_OLLAMA
    etiqueta = _formatear_proveedor(PROVEEDOR_OLLAMA)
    assert "solo en tu laptop" in etiqueta.lower(), f"La opción debe indicar 'solo en tu laptop': {etiqueta}"


def test_t79_seccion_terminos_ingles_en_modo_demo():
    """T79: La sección 'Términos en inglés' aparece en modo demo en la plantilla Ponencia y textos estudiantiles."""
    at = AppTest.from_file(str(ROOT_DIR / "app" / "streamlit_app.py"), default_timeout=30)
    at.run()

    # Activar modo demo
    demo_toggle = [t for t in at.toggle if "demo" in (t.label or "").lower()][0]
    demo_toggle.set_value(True).run()

    # Seleccionar Ponencia / Clase / Charla
    at.selectbox[0].select("Ponencia / Clase / Charla").run()
    assert not at.exception, f"Excepción en modo demo: {at.exception}"

    # Verificar que aparece el encabezado de Términos en inglés
    textos_markdown = [m.value for m in at.markdown]
    assert any("Términos en inglés" in m for m in textos_markdown), (
        "Debe mostrarse la sección 'Términos en inglés' en modo demo"
    )

    # Verificar que el texto de opciones avanzadas dice 'Términos en inglés que esperas escuchar'
    # y NO 'Glosario contextual de investigación'
    textos_area = [ta.label for ta in at.text_area]
    assert any("Términos en inglés que esperas escuchar" in t for t in textos_area), (
        "El text_area de glosario debe llamarse 'Términos en inglés que esperas escuchar (opcional):'"
    )
    assert not any("Glosario contextual de investigación" in t for t in textos_area), (
        "No debe quedar texto de 'Glosario contextual de investigación'"
    )
