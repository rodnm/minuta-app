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
