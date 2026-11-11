"""Pruebas unitarias para el esqueleto de la aplicación Streamlit (T06).

Valida:
- Carga y validación con Pydantic v2 de fixtures de las 3 plantillas y transcripciones.
- Generación del HTML autónomo de markmap con CDN fija sin requerir servidor Streamlit.
- Extracción de nodos con marcas de tiempo [mm:ss] y citas literales.
- Funciones de apoyo de tiempo y glosario.
- Simulación de renderizado sin excepciones vía Streamlit AppTest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from minuta.esquemas import (
    NodoMapa,
    MapaMental,
    ResultadoPonencia,
    ResultadoReunion,
    ResultadoEntrevista,
    Transcripcion,
)
from app.streamlit_app import (
    generar_html_markmap,
    segundos_a_tiempo,
    extraer_nodos_con_tiempo,
    cargar_fixture_demo,
    PLANTILLAS_DISPONIBLES,
    GLOSARIO_DEFECTO,
    VERSION_MARKMAP_CDN,
)


@pytest.fixture(autouse=True)
def entorno_sin_claves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que la app lea el .env real y cargue una clave en el proceso de pytest."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)


def test_segundos_a_tiempo() -> None:
    """Verifica el formateo de segundos a formato [mm:ss]."""
    assert segundos_a_tiempo(0.0) == "[00:00]"
    assert segundos_a_tiempo(75.0) == "[01:15]"
    assert segundos_a_tiempo(600.0) == "[10:00]"
    assert segundos_a_tiempo(3665.0) == "[61:05]"


def test_glosario_defecto_contiene_terminos_clave() -> None:
    """Verifica que el glosario inicial incluya términos universitarios en inglés."""
    assert "machine learning" in GLOSARIO_DEFECTO
    assert "JSON" in GLOSARIO_DEFECTO
    assert "prompt" in GLOSARIO_DEFECTO
    assert "pipeline" in GLOSARIO_DEFECTO
    assert "benchmark" in GLOSARIO_DEFECTO


def test_cargar_fixture_demo_ponencia() -> None:
    """Carga y valida con el esquema Pydantic el fixture de Ponencia."""
    resultado, transcripcion = cargar_fixture_demo("Ponencia / Clase / Charla")
    assert isinstance(resultado, ResultadoPonencia)
    assert isinstance(resultado.mapa, MapaMental)
    assert len(resultado.ideas_clave) > 0
    assert transcripcion is not None
    assert isinstance(transcripcion, Transcripcion)
    assert transcripcion.duracion_s > 0


def test_cargar_fixture_demo_reunion() -> None:
    """Carga y valida con el esquema Pydantic el fixture de Reunión."""
    resultado, transcripcion = cargar_fixture_demo("Reunión")
    assert isinstance(resultado, ResultadoReunion)
    assert len(resultado.tareas) > 0
    assert len(resultado.acuerdos) > 0
    assert transcripcion is not None
    assert isinstance(transcripcion, Transcripcion)


def test_cargar_fixture_demo_entrevista() -> None:
    """Carga y valida con el esquema Pydantic el fixture de Entrevista."""
    resultado, transcripcion = cargar_fixture_demo("Entrevista")
    assert isinstance(resultado, ResultadoEntrevista)
    assert len(resultado.libro) > 0
    assert len(resultado.fragmentos) > 0
    assert transcripcion is not None
    assert isinstance(transcripcion, Transcripcion)


def test_cargar_fixture_demo_invalido() -> None:
    """Verifica que una plantilla desconocida lance ValueError."""
    with pytest.raises(ValueError, match="Plantilla no reconocida"):
        cargar_fixture_demo("Inexistente")


def test_extraer_nodos_con_tiempo_desde_arbol() -> None:
    """Extrae nodos del árbol que poseen evidencia y verifica sus marcas temporales."""
    resultado, _ = cargar_fixture_demo("Ponencia / Clase / Charla")
    nodos = extraer_nodos_con_tiempo(resultado.mapa.raiz)

    assert len(nodos) > 0
    for nodo in nodos:
        assert "id" in nodo
        assert "titulo" in nodo
        assert "inicio_s" in nodo
        assert "tiempo_tag" in nodo
        assert "cita" in nodo
        assert nodo["tiempo_tag"].startswith("[") and nodo["tiempo_tag"].endswith("]")
        assert nodo["inicio_s"] >= 0.0

    titulos = [n["titulo"] for n in nodos]
    assert "Proceso Editorial" in titulos
    assert "Respuesta a Revisor" in titulos


def test_generar_html_markmap_contiene_cdn_fija_y_markdown() -> None:
    """Verifica que el HTML contenga el autoloader con versión fija y el markdown."""
    markdown_muestra = "# Tema Principal\n## Subtema [01:30]\nDetalle explicativo"
    html = generar_html_markmap(markdown_muestra)

    assert f"markmap-autoloader@{VERSION_MARKMAP_CDN}" in html
    assert "cdn.jsdelivr.net" in html
    assert '<div class="markmap">' in html
    assert "# Tema Principal" in html
    assert "## Subtema [01:30]" in html
    assert "markmap.autoLoader" in html


def test_generar_html_markmap_arbol_vacio() -> None:
    """Verifica la generación de HTML con árbol vacío sin generar excepciones."""
    html = generar_html_markmap("")
    assert '<div class="markmap">' in html
    assert f"markmap-autoloader@{VERSION_MARKMAP_CDN}" in html


def test_app_test_render_modo_demo() -> None:
    """Ejecuta la aplicación completa en modo demo con Streamlit AppTest y verifica ausencia de excepciones."""
    app = AppTest.from_file(str(ROOT_DIR / "app" / "streamlit_app.py"))
    app.run()
    assert not app.exception, f"Excepción en AppTest: {app.exception}"
    assert any("MINUTA" in m.value for m in app.markdown)  # encabezado de marca

    # El modo demo arranca apagado (L51 B5); al activarlo se muestra el ejemplo sin excepciones.
    app.toggle[0].set_value(True).run()
    assert not app.exception, f"Excepción en modo demo: {app.exception}"
    assert any("Modo demo activo" in s.value for s in app.success)
