"""Pruebas unitarias para la exportación multi-formato y componente HTML Markmap (T14).

Cubre:
- minuta.exportar:
  - exportar_markdown (Ponencia, Reunión, Entrevista)
  - exportar_mapa_html (HTML autónomo con markmap-autoloader@0.17.2)
  - exportar_docx (documento Word con tablas y estilos)
  - exportar_xlsx (libro Excel con hojas estructuradas)
- minuta.mapa_html:
  - generar_componente_markmap (componente Streamlit/Web responsivo)
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import pytest
import docx
import openpyxl

from minuta.esquemas import (
    ResultadoPonencia,
    ResultadoReunion,
    ResultadoEntrevista,
    MapaMental,
    NodoMapa,
    Evidencia,
    Tarea,
    Acuerdo,
    Pendiente,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"


@pytest.fixture
def ponencia_fixture() -> ResultadoPonencia:
    ruta = FIXTURES_DIR / "resultado_ponencia.json"
    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return ResultadoPonencia.model_validate(datos)


@pytest.fixture
def reunion_fixture() -> ResultadoReunion:
    ruta = FIXTURES_DIR / "resultado_reunion.json"
    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return ResultadoReunion.model_validate(datos)


@pytest.fixture
def entrevista_fixture() -> ResultadoEntrevista:
    ruta = FIXTURES_DIR / "resultado_entrevista.json"
    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return ResultadoEntrevista.model_validate(datos)


# ==============================================================================
# Pruebas de minuta.mapa_html
# ==============================================================================


def test_generar_componente_markmap_basico(ponencia_fixture: ResultadoPonencia):
    from minuta.mapa_html import generar_componente_markmap

    html_code = generar_componente_markmap(ponencia_fixture.mapa, altura_px=500)
    assert isinstance(html_code, str)
    assert "https://cdn.jsdelivr.net/npm/markmap-autoloader@0.17.2" in html_code
    assert "markmap" in html_code
    assert "500px" in html_code
    assert ponencia_fixture.mapa.titulo in html_code
    assert "viewport" in html_code
    assert "</script>" not in html_code.split("<script type=\"text/template\">")[1].split("</script>")[0]


def test_generar_componente_markmap_altura_defecto(reunion_fixture: ResultadoReunion):
    from minuta.mapa_html import generar_componente_markmap

    html_code = generar_componente_markmap(reunion_fixture.mapa)
    assert "450px" in html_code
    assert reunion_fixture.mapa.titulo in html_code


# ==============================================================================
# Pruebas de exportar_mapa_html
# ==============================================================================


def test_exportar_mapa_html_autonomo(ponencia_fixture: ResultadoPonencia):
    from minuta.exportar import exportar_mapa_html

    titulo_custom = "Mapa Mental: Estrategias de Publicación"
    html_doc = exportar_mapa_html(ponencia_fixture.mapa, titulo=titulo_custom)

    assert "<!DOCTYPE html>" in html_doc
    assert f"<title>{titulo_custom}</title>" in html_doc
    assert "https://cdn.jsdelivr.net/npm/markmap-autoloader@0.17.2" in html_doc
    assert "markmap-autoloader" in html_doc
    assert "viewport" in html_doc
    assert ponencia_fixture.mapa.titulo in html_doc


# ==============================================================================
# Pruebas de exportar_markdown
# ==============================================================================


def test_exportar_markdown_ponencia(ponencia_fixture: ResultadoPonencia):
    from minuta.exportar import exportar_markdown

    md = exportar_markdown(ponencia_fixture)
    assert isinstance(md, str)
    assert "# Minuta: Ponencia / Clase / Charla" in md
    assert "## Resumen General" in md
    assert ponencia_fixture.resumen_general in md
    assert "## Ideas Clave" in md
    assert "## Mapa Mental" in md
    assert ponencia_fixture.mapa.titulo in md
    # Verificar que contiene las ideas clave y sus evidencias
    assert "Estrategias de publicación" in md
    assert "[00:15]" in md or "[0:15]" in md or "00:15" in md


def test_exportar_markdown_reunion(reunion_fixture: ResultadoReunion):
    from minuta.exportar import exportar_markdown

    md = exportar_markdown(reunion_fixture)
    assert "# Minuta: Reunión de Trabajo" in md
    assert "## Resumen General" in md
    assert "## Tareas y To-Do" in md or "## Tareas" in md
    assert "## Acuerdos" in md
    assert "## Mapa Mental" in md
    assert "Andrea" in md
    assert "Carlos" in md
    assert "mmBERT-small" in md


def test_exportar_markdown_entrevista(entrevista_fixture: ResultadoEntrevista):
    from minuta.exportar import exportar_markdown

    md = exportar_markdown(entrevista_fixture)
    assert "# Minuta: Entrevista de Investigación" in md
    assert "## Libro de Códigos" in md
    assert "BARR_TIEMPO" in md
    assert "USO_IA" in md
    assert "## Resumen por Código" in md
    assert "## Fragmentos Codificados" in md
    assert "## Mapa Mental" in md


# ==============================================================================
# Pruebas de exportar_docx
# ==============================================================================


def test_exportar_docx_reunion_bytes_y_archivo(reunion_fixture: ResultadoReunion, tmp_path: Path):
    from minuta.exportar import exportar_docx

    ruta_archivo = tmp_path / "minuta_reunion.docx"
    docx_bytes = exportar_docx(reunion_fixture, ruta_salida=ruta_archivo)

    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0
    assert ruta_archivo.exists()
    assert ruta_archivo.stat().st_size == len(docx_bytes)

    # Validar que es un documento Word válido
    doc = docx.Document(io.BytesIO(docx_bytes))
    texto_completo = " ".join(p.text for p in doc.paragraphs)
    assert "Reunión" in texto_completo
    assert "Resumen General" in texto_completo

    # Validar tablas
    assert len(doc.tables) >= 1
    tabla_texto = " ".join(cell.text for row in doc.tables[0].rows for cell in row.cells)
    assert "Andrea" in tabla_texto or "Carlos" in tabla_texto or "Tareas" in tabla_texto


def test_exportar_docx_ponencia(ponencia_fixture: ResultadoPonencia):
    from minuta.exportar import exportar_docx

    docx_bytes = exportar_docx(ponencia_fixture)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0

    doc = docx.Document(io.BytesIO(docx_bytes))
    texto_completo = " ".join(p.text for p in doc.paragraphs)
    assert "Ponencia" in texto_completo
    assert "Ideas Clave" in texto_completo


def test_exportar_docx_entrevista(entrevista_fixture: ResultadoEntrevista):
    from minuta.exportar import exportar_docx

    docx_bytes = exportar_docx(entrevista_fixture)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0

    doc = docx.Document(io.BytesIO(docx_bytes))
    texto_completo = " ".join(p.text for p in doc.paragraphs)
    assert "Entrevista" in texto_completo
    assert "Libro de Códigos" in texto_completo or "Códigos" in texto_completo


# ==============================================================================
# Pruebas de exportar_xlsx
# ==============================================================================


def test_exportar_xlsx_reunion_bytes_y_archivo(reunion_fixture: ResultadoReunion, tmp_path: Path):
    from minuta.exportar import exportar_xlsx

    ruta_archivo = tmp_path / "minuta_reunion.xlsx"
    xlsx_bytes = exportar_xlsx(reunion_fixture, ruta_salida=ruta_archivo)

    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0
    assert ruta_archivo.exists()
    assert ruta_archivo.stat().st_size == len(xlsx_bytes)

    # Validar con openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert "Tareas y Acuerdos" in wb.sheetnames or "Tareas" in wb.sheetnames

    hoja = wb["Tareas y Acuerdos"] if "Tareas y Acuerdos" in wb.sheetnames else wb["Tareas"]
    filas = list(hoja.iter_rows(values_only=True))
    assert len(filas) >= 2  # Encabezado + filas de datos

    encabezados = [str(col).lower() for col in filas[0] if col is not None]
    assert any("descripci" in h for h in encabezados)
    assert any("responsable" in h for h in encabezados)
    assert any("cita" in h for h in encabezados)

    # Verificar que los datos de las tareas están presentes
    valores_celdas = " ".join(str(val) for fila in filas for val in fila if val is not None)
    assert "Andrea" in valores_celdas
    assert "Carlos" in valores_celdas


def test_exportar_xlsx_ponencia(ponencia_fixture: ResultadoPonencia):
    from minuta.exportar import exportar_xlsx

    xlsx_bytes = exportar_xlsx(ponencia_fixture)
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert len(wb.sheetnames) >= 1
    hoja = wb.active
    filas = list(hoja.iter_rows(values_only=True))
    assert len(filas) >= 2
    valores_celdas = " ".join(str(val) for fila in filas for val in fila if val is not None)
    assert "Estrategias de publicación" in valores_celdas or "Scopus" in valores_celdas


def test_exportar_xlsx_entrevista(entrevista_fixture: ResultadoEntrevista):
    from minuta.exportar import exportar_xlsx

    xlsx_bytes = exportar_xlsx(entrevista_fixture)
    assert isinstance(xlsx_bytes, bytes)
    assert len(xlsx_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert len(wb.sheetnames) >= 1
    valores_celdas = " ".join(
        str(val)
        for name in wb.sheetnames
        for fila in wb[name].iter_rows(values_only=True)
        for val in fila
        if val is not None
    )
    assert "BARR_TIEMPO" in valores_celdas
    assert "USO_IA" in valores_celdas


# ==============================================================================
# Casos de borde / Resiliencia
# ==============================================================================


def test_exportar_reunion_sin_tareas_ni_acuerdos():
    from minuta.exportar import exportar_markdown, exportar_docx, exportar_xlsx

    mapa = MapaMental(
        titulo="Reunión Vacía",
        raiz=NodoMapa(id="raiz", titulo="Inicio"),
    )
    reunion_vacia = ResultadoReunion(
        resumen_general="Sin acuerdos formales.",
        temas=[],
        acuerdos=[],
        tareas=[],
        pendientes=[],
        mapa=mapa,
    )

    md = exportar_markdown(reunion_vacia)
    assert "Sin acuerdos formales." in md

    docx_bytes = exportar_docx(reunion_vacia)
    assert len(docx_bytes) > 0
    doc = docx.Document(io.BytesIO(docx_bytes))
    assert len(doc.paragraphs) > 0

    xlsx_bytes = exportar_xlsx(reunion_vacia)
    assert len(xlsx_bytes) > 0
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert len(wb.sheetnames) >= 1
