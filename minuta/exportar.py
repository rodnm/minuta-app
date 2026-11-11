"""Módulo de exportación multi-formato para Minuta (T14).

Soporta exportación a:
- Markdown (.md)
- HTML interactivo autónomo con Markmap (.html)
- Microsoft Word (.docx) con python-docx
- Microsoft Excel (.xlsx) con openpyxl

Diseñado siguiendo principios de accesibilidad, legibilidad en pantallas
móviles y estilo profesional para investigación académica y gestión ejecutiva.
"""

from __future__ import annotations

import html
import io
from pathlib import Path
from typing import Any

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from minuta.esquemas import (
    ResultadoPonencia,
    ResultadoReunion,
    ResultadoEntrevista,
    MapaMental,
    NodoMapa,
    Transcripcion,
)

VERSION_MARKMAP_CDN = "0.17.2"


def _segundos_a_tiempo(segundos: float) -> str:
    """Convierte segundos a formato de visualización [mm:ss]."""
    seg = max(0, int(round(segundos)))
    minutos = seg // 60
    restantes = seg % 60
    return f"[{minutos:02d}:{restantes:02d}]"


def _formatear_arbol_como_esquema_md(nodo: NodoMapa, nivel: int = 0) -> list[str]:
    """Formatea recursivamente un árbol de nodos como lista indentada con minutos y citas."""
    lineas: list[str] = []
    prefijo = "  " * nivel
    tag = f" `{_segundos_a_tiempo(nodo.evidencia.inicio_s)}`" if nodo.evidencia else ""
    lineas.append(f"{prefijo}- **{nodo.titulo}**{tag}")
    if nodo.resumen:
        lineas.append(f"{prefijo}  _{nodo.resumen}_")
    if nodo.evidencia:
        lineas.append(f"{prefijo}  > \"{nodo.evidencia.cita}\"")
    for hijo in nodo.hijos:
        lineas.extend(_formatear_arbol_como_esquema_md(hijo, nivel + 1))
    return lineas


# ==============================================================================
# 1. EXPORTACIÓN A MARKDOWN
# ==============================================================================


def exportar_markdown(
    resultado: ResultadoPonencia | ResultadoReunion | ResultadoEntrevista,
    transcripcion: Transcripcion | None = None,
) -> str:
    """Genera un documento Markdown completo, elegante y bien estructurado según la plantilla.

    Args:
        resultado: Resultado estructurado de Ponencia, Reunión o Entrevista.
        transcripcion: Transcripción completa opcional a anexar.

    Returns:
        Cadena de texto con el Markdown listo para ser compartido o guardado.
    """
    lineas: list[str] = []

    if isinstance(resultado, ResultadoPonencia):
        lineas.append("# Minuta: Notas de clase (Ponencia / Charla)")
        lineas.append("")
        lineas.append(f"**Tema central:** {resultado.mapa.titulo}  ")
        lineas.append(f"**Modo de procesamiento:** `{resultado.modo}`  ")
        if resultado.descartados > 0:
            lineas.append(f"**Segmentos descartados sin cita literal:** {resultado.descartados}  ")
        lineas.append("")

        lineas.append("## Resumen General")
        lineas.append("")
        lineas.append(resultado.resumen_general)
        lineas.append("")

        lineas.append("## Ideas Clave")
        lineas.append("")
        for idea in resultado.ideas_clave:
            lineas.append(f"### {idea.titulo}")
            lineas.append(idea.resumen)
            lineas.append("")
            if idea.evidencias:
                lineas.append("**Evidencias literales:**")
                for ev in idea.evidencias:
                    tag = _segundos_a_tiempo(ev.inicio_s)
                    lineas.append(f"- > {tag} \"{ev.cita}\"")
                lineas.append("")

        lineas.append("## Preguntas y Pendientes")
        lineas.append("")
        if resultado.preguntas:
            for p in resultado.preguntas:
                tag = _segundos_a_tiempo(p.evidencia.inicio_s)
                lineas.append(f"- **Pregunta:** {p.descripcion}")
                lineas.append(f"  > {tag} \"{p.evidencia.cita}\"")
            lineas.append("")
        else:
            lineas.append("_No se registraron preguntas abiertas ni temas pendientes._\n")

        lineas.append("## Mapa Mental")
        lineas.append("")
        lineas.append(resultado.mapa.to_markdown())
        lineas.append("")

    elif isinstance(resultado, ResultadoReunion):
        lineas.append("# Minuta: Notas de reunión")
        lineas.append("")
        lineas.append(f"**Tema central:** {resultado.mapa.titulo}  ")
        lineas.append(f"**Modo de procesamiento:** `{resultado.modo}`  ")
        if resultado.descartados > 0:
            lineas.append(f"**Segmentos descartados sin cita literal:** {resultado.descartados}  ")
        lineas.append("")

        lineas.append("## Resumen General")
        lineas.append("")
        lineas.append(resultado.resumen_general)
        lineas.append("")

        lineas.append("## Temas Tratados")
        lineas.append("")
        for tema in resultado.temas:
            lineas.append(f"### {tema.titulo}")
            lineas.append(tema.resumen)
            lineas.append("")
            if tema.evidencias:
                lineas.append("**Evidencias literales:**")
                for ev in tema.evidencias:
                    tag = _segundos_a_tiempo(ev.inicio_s)
                    lineas.append(f"- > {tag} \"{ev.cita}\"")
                lineas.append("")

        lineas.append("## Tareas y To-Do")
        lineas.append("")
        if resultado.tareas:
            for t in resultado.tareas:
                resp = f" *(Responsable: {t.responsable})*" if t.responsable else ""
                limite = f" *(Límite: {t.fecha_limite})*" if t.fecha_limite else ""
                tag = _segundos_a_tiempo(t.evidencia.inicio_s)
                lineas.append(f"- [ ] **{t.descripcion}**{resp}{limite}")
                lineas.append(f"  > {tag} \"{t.evidencia.cita}\"")
            lineas.append("")
        else:
            lineas.append("_No se asignaron tareas pendientes en esta reunión._\n")

        lineas.append("## Acuerdos")
        lineas.append("")
        if resultado.acuerdos:
            for a in resultado.acuerdos:
                tag = _segundos_a_tiempo(a.evidencia.inicio_s)
                lineas.append(f"- **Acuerdo:** {a.descripcion}")
                lineas.append(f"  > {tag} \"{a.evidencia.cita}\"")
            lineas.append("")
        else:
            lineas.append("_No se registraron acuerdos formales._\n")

        lineas.append("## Preguntas y Pendientes")
        lineas.append("")
        if resultado.pendientes:
            for p in resultado.pendientes:
                tag = _segundos_a_tiempo(p.evidencia.inicio_s)
                lineas.append(f"- **Pendiente:** {p.descripcion}")
                lineas.append(f"  > {tag} \"{p.evidencia.cita}\"")
            lineas.append("")
        else:
            lineas.append("_No quedaron preguntas pendientes de resolución._\n")

    elif isinstance(resultado, ResultadoEntrevista):
        lineas.append("# Minuta: Esquema por temas (Entrevista / Conversación)")
        lineas.append("")
        lineas.append(f"**Tema central:** {resultado.mapa.titulo}  ")
        lineas.append(f"**Modo de procesamiento:** `{resultado.modo}`  ")
        if resultado.descartados > 0:
            lineas.append(f"**Segmentos descartados sin cita literal:** {resultado.descartados}  ")
        lineas.append("")

        lineas.append("## Resumen por Código")
        lineas.append("")
        for codigo, texto in resultado.resumen_por_codigo.items():
            lineas.append(f"### Código: {codigo}")
            lineas.append(texto)
            lineas.append("")

        lineas.append("## Esquema por Temas")
        lineas.append("")
        lineas.extend(_formatear_arbol_como_esquema_md(resultado.mapa.raiz))
        lineas.append("")

        lineas.append("## Códigos temáticos")
        lineas.append("")
        for cod in resultado.libro:
            lineas.append(f"- **`{cod.codigo}`**: {cod.descripcion}")
        lineas.append("")

        lineas.append("## Fragmentos Codificados")
        lineas.append("")
        for f in resultado.fragmentos:
            tag = _segundos_a_tiempo(f.evidencia.inicio_s)
            nota = f" *(Nota: {f.nota})*" if f.nota else ""
            lineas.append(f"- **[{f.codigo}]**{nota}")
            lineas.append(f"  > {tag} \"{f.evidencia.cita}\"")
        lineas.append("")

    terminos = getattr(resultado, "terminos_ingles", [])
    if terminos:
        lineas.append("## Términos en inglés")
        lineas.append("")
        for t in terminos:
            tag = _segundos_a_tiempo(t.evidencia.inicio_s)
            extra = f" *(se transcribió «{t.transcrito}»)*" if t.transcrito.strip().lower() != t.termino.strip().lower() else ""
            lineas.append(f"- **{t.termino}**{extra} `{tag}`")
            lineas.append(f"  > \"{t.evidencia.cita}\"")
        lineas.append("")

    if transcripcion is not None:
        lineas.append("## Transcripción Completa")
        lineas.append("")
        for seg in transcripcion.segmentos:
            tag = f"[{_segundos_a_tiempo(seg.inicio_s)} → {_segundos_a_tiempo(seg.fin_s)}]"
            lineas.append(f"- **{tag}** {seg.texto}")
        lineas.append("")

    return "\n".join(lineas)


# ==============================================================================
# 2. EXPORTACIÓN A HTML AUTÓNOMO (MARKMAP)
# ==============================================================================


def exportar_mapa_html(mapa: MapaMental, titulo: str = "Mapa Mental - Minuta") -> str:
    """Genera un archivo HTML autónomo completo para visualizar el mapa mental.

    Utiliza markmap-autoloader con versión fija de CDN jsDelivr y estilos
    responsivos para escritorio y teléfonos celulares.

    Args:
        mapa: Árbol MapaMental a renderizar.
        titulo: Título visible en la pestaña del navegador y encabezado.

    Returns:
        Cadena con el código HTML listo para ser guardado como archivo .html.
    """
    markdown_arbol = mapa.to_markdown()
    markdown_seguro = markdown_arbol.replace("</script>", "<\\/script>")
    titulo_escapado = html.escape(titulo)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=yes">
  <title>{titulo_escapado}</title>
  <style>
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background-color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    header {{
      background: #1e293b;
      color: #ffffff;
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      z-index: 10;
      flex-shrink: 0;
    }}
    header h1 {{
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      letter-spacing: -0.2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .badge {{
      background: #3b82f6;
      color: #ffffff;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .map-wrapper {{
      position: relative;
      flex: 1;
      width: 100%;
      height: 100%;
      background: #ffffff;
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
    .floating-help {{
      position: absolute;
      bottom: 16px;
      right: 16px;
      background: rgba(255, 255, 255, 0.92);
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 12px;
      color: #475569;
      box-shadow: 0 2px 5px rgba(0,0,0,0.08);
      pointer-events: none;
      user-select: none;
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@{VERSION_MARKMAP_CDN}"></script>
</head>
<body>
  <header>
    <h1>{titulo_escapado}</h1>
    <span class="badge">Minuta</span>
  </header>
  <div class="map-wrapper">
    <div class="markmap">
      <script type="text/template">
{markdown_seguro}
      </script>
    </div>
    <div class="floating-help">📱 Pellizca para zoom · Arrastra para navegar</div>
  </div>
  <script>
    function renderizar() {{
      if (window.markmap && window.markmap.autoLoader) {{
        window.markmap.autoLoader.renderAll();
      }}
    }}
    window.addEventListener("DOMContentLoaded", renderizar);
    window.addEventListener("load", renderizar);
    if (document.readyState === "complete" || document.readyState === "interactive") {{
      setTimeout(renderizar, 60);
    }}
  </script>
</body>
</html>"""


# ==============================================================================
# 3. EXPORTACIÓN A WORD (.DOCX)
# ==============================================================================


def _formatear_parrafo_evidencia(p: Any, tiempo_str: str, cita: str) -> None:
    """Añade una cita textual con sangría y estilo cursiva en Word."""
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_after = Pt(4)
    run_tag = p.add_run(f"{tiempo_str} ")
    run_tag.bold = True
    run_tag.font.color.rgb = RGBColor(13, 110, 253)  # Azul Minuta
    run_cita = p.add_run(f'"{cita}"')
    run_cita.italic = True
    run_cita.font.color.rgb = RGBColor(100, 116, 139)


def exportar_docx(
    resultado: ResultadoPonencia | ResultadoReunion | ResultadoEntrevista,
    transcripcion: Transcripcion | None = None,
    ruta_salida: str | Path | None = None,
) -> bytes:
    """Genera un documento Microsoft Word (.docx) profesional y estilizado según la plantilla.

    Args:
        resultado: Estructuración de Ponencia, Reunión o Entrevista.
        transcripcion: Transcripción completa opcional a anexar.
        ruta_salida: Ruta opcional donde guardar el archivo en disco.

    Returns:
        Bytes correspondientes al archivo binario .docx.
    """
    if isinstance(transcripcion, (str, Path)):
        ruta_salida = transcripcion
        transcripcion = None

    doc = docx.Document()

    # Configuración de márgenes
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Encabezado principal
    if isinstance(resultado, ResultadoPonencia):
        nombre_tipo = "Notas de clase (Ponencia / Charla)"
    elif isinstance(resultado, ResultadoReunion):
        nombre_tipo = "Notas de reunión"
    else:
        nombre_tipo = "Esquema por temas (Entrevista / Conversación)"

    h1 = doc.add_heading(f"Minuta: {nombre_tipo}", level=1)
    h1.alignment = WD_ALIGN_PARAGRAPH.LEFT

    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_after = Pt(12)
    r_tema = p_meta.add_run(f"Tema central: {resultado.mapa.titulo}\n")
    r_tema.bold = True
    p_meta.add_run(f"Modo: {resultado.modo} · Segmentos descartados: {resultado.descartados}")

    # Resumen General o por código
    if hasattr(resultado, "resumen_general"):
        doc.add_heading("Resumen General", level=2)
        p_res = doc.add_paragraph(resultado.resumen_general)
        p_res.paragraph_format.space_after = Pt(10)

    if isinstance(resultado, ResultadoPonencia):
        doc.add_heading("Ideas Clave", level=2)
        for idea in resultado.ideas_clave:
            doc.add_heading(idea.titulo, level=3)
            doc.add_paragraph(idea.resumen)
            for ev in idea.evidencias:
                p_ev = doc.add_paragraph()
                _formatear_parrafo_evidencia(p_ev, _segundos_a_tiempo(ev.inicio_s), ev.cita)

        doc.add_heading("Preguntas y Pendientes", level=2)
        if resultado.preguntas:
            for p in resultado.preguntas:
                p_item = doc.add_paragraph(style="List Bullet")
                r_tit = p_item.add_run(f"{p.descripcion}\n")
                r_tit.bold = True
                _formatear_parrafo_evidencia(p_item, _segundos_a_tiempo(p.evidencia.inicio_s), p.evidencia.cita)
        else:
            doc.add_paragraph("No se registraron preguntas ni temas pendientes.")

        # Sección: Mapa mental jerárquico solo para Ponencia / Clase
        doc.add_heading("Estructura del Mapa Mental", level=2)

        def _recorrer_nodo_docx(nodo: NodoMapa, nivel: int) -> None:
            p_nodo = doc.add_paragraph()
            p_nodo.paragraph_format.left_indent = Inches(0.2 * nivel)
            tag = nodo.tiempo_tag()
            tag_str = f" {tag}" if tag else ""
            run_tit = p_nodo.add_run(f"{'• ' if nivel > 1 else '■ '}{nodo.titulo}{tag_str}")
            if nivel == 1:
                run_tit.bold = True
                run_tit.font.size = Pt(13)
            elif nivel == 2:
                run_tit.bold = True
                run_tit.font.size = Pt(11)
            else:
                run_tit.font.size = Pt(10.5)

            if nodo.resumen:
                p_res = doc.add_paragraph()
                p_res.paragraph_format.left_indent = Inches(0.2 * nivel + 0.15)
                r_r = p_res.add_run(nodo.resumen)
                r_r.italic = True
                r_r.font.size = Pt(10)

            for hijo in nodo.hijos:
                _recorrer_nodo_docx(hijo, nivel + 1)

        _recorrer_nodo_docx(resultado.mapa.raiz, 1)

    elif isinstance(resultado, ResultadoReunion):
        # 1. Tabla de Tareas (To-Do)
        doc.add_heading("Tareas y Compromisos (To-Do)", level=2)
        if resultado.tareas:
            tabla_t = doc.add_table(rows=1, cols=4)
            tabla_t.alignment = WD_TABLE_ALIGNMENT.CENTER
            hdr_cells = tabla_t.rows[0].cells
            hdr_cells[0].text = "Descripción"
            hdr_cells[1].text = "Responsable"
            hdr_cells[2].text = "Límite"
            hdr_cells[3].text = "Minuto y Cita"

            for cell in hdr_cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True

            for t in resultado.tareas:
                row_cells = tabla_t.add_row().cells
                row_cells[0].text = t.descripcion
                row_cells[1].text = t.responsable or "-"
                row_cells[2].text = t.fecha_limite or "-"
                tag = _segundos_a_tiempo(t.evidencia.inicio_s)
                row_cells[3].text = f'{tag} "{t.evidencia.cita}"'

            doc.add_paragraph().paragraph_format.space_after = Pt(10)
        else:
            doc.add_paragraph("No se registraron tareas pendientes.")

        # 2. Acuerdos
        doc.add_heading("Acuerdos Adoptados", level=2)
        if resultado.acuerdos:
            for a in resultado.acuerdos:
                p_ac = doc.add_paragraph(style="List Bullet")
                r_ac = p_ac.add_run(f"{a.descripcion}\n")
                r_ac.bold = True
                _formatear_parrafo_evidencia(p_ac, _segundos_a_tiempo(a.evidencia.inicio_s), a.evidencia.cita)
        else:
            doc.add_paragraph("No se formalizaron acuerdos.")

        # 3. Temas Tratados
        doc.add_heading("Temas Tratados", level=2)
        for tema in resultado.temas:
            doc.add_heading(tema.titulo, level=3)
            doc.add_paragraph(tema.resumen)
            for ev in tema.evidencias:
                p_ev = doc.add_paragraph()
                _formatear_parrafo_evidencia(p_ev, _segundos_a_tiempo(ev.inicio_s), ev.cita)

        # 4. Pendientes
        doc.add_heading("Preguntas y Pendientes", level=2)
        if resultado.pendientes:
            for pend in resultado.pendientes:
                p_pend = doc.add_paragraph(style="List Bullet")
                r_pend = p_pend.add_run(f"{pend.descripcion}\n")
                r_pend.bold = True
                _formatear_parrafo_evidencia(p_pend, _segundos_a_tiempo(pend.evidencia.inicio_s), pend.evidencia.cita)
        else:
            doc.add_paragraph("No quedaron temas pendientes.")

    elif isinstance(resultado, ResultadoEntrevista):
        doc.add_heading("Códigos temáticos", level=2)
        tabla_cod = doc.add_table(rows=1, cols=2)
        tabla_cod.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cod = tabla_cod.rows[0].cells
        hdr_cod[0].text = "Código"
        hdr_cod[1].text = "Descripción"
        for cell in hdr_cod:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True

        for c in resultado.libro:
            row = tabla_cod.add_row().cells
            row[0].text = c.codigo
            row[1].text = c.descripcion

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

        doc.add_heading("Resumen por Código Temático", level=2)
        for cod, res_c in resultado.resumen_por_codigo.items():
            doc.add_heading(f"Código [{cod}]", level=3)
            doc.add_paragraph(res_c)

        # Esquema jerárquico por temas con indentación
        doc.add_heading("Esquema Jerárquico por Temas", level=2)

        def _recorrer_nodo_esquema_docx(nodo: NodoMapa, nivel: int) -> None:
            p_nodo = doc.add_paragraph(style="List Bullet")
            p_nodo.paragraph_format.left_indent = Inches(0.25 * max(1, nivel))
            tag = nodo.tiempo_tag()
            tag_str = f" {tag}" if tag else ""
            run_tit = p_nodo.add_run(f"{nodo.titulo}{tag_str}")
            run_tit.bold = True
            if nodo.resumen:
                p_nodo.add_run(f" — {nodo.resumen}")
            if nodo.evidencia:
                p_ev = doc.add_paragraph()
                p_ev.paragraph_format.left_indent = Inches(0.25 * max(1, nivel) + 0.2)
                _formatear_parrafo_evidencia(p_ev, _segundos_a_tiempo(nodo.evidencia.inicio_s), nodo.evidencia.cita)

            for hijo in nodo.hijos:
                _recorrer_nodo_esquema_docx(hijo, nivel + 1)

        _recorrer_nodo_esquema_docx(resultado.mapa.raiz, 1)

        doc.add_heading("Fragmentos Codificados", level=2)
        for f in resultado.fragmentos:
            p_f = doc.add_paragraph(style="List Bullet")
            r_c = p_f.add_run(f"[{f.codigo}]")
            r_c.bold = True
            if f.nota:
                p_f.add_run(f" — Nota: {f.nota}\n")
            else:
                p_f.add_run("\n")
            _formatear_parrafo_evidencia(p_f, _segundos_a_tiempo(f.evidencia.inicio_s), f.evidencia.cita)

    terminos = getattr(resultado, "terminos_ingles", [])
    if terminos:
        doc.add_heading("Términos en inglés", level=2)
        for t in terminos:
            p_term = doc.add_paragraph(style="List Bullet")
            extra = f" (se transcribió «{t.transcrito}»)" if t.transcrito.strip().lower() != t.termino.strip().lower() else ""
            r_tit = p_term.add_run(f"{t.termino}{extra}\n")
            r_tit.bold = True
            _formatear_parrafo_evidencia(p_term, _segundos_a_tiempo(t.evidencia.inicio_s), t.evidencia.cita)

    # Anexar transcripción si se proveyó
    if transcripcion is not None:
        doc.add_heading("Transcripción Completa", level=2)
        for seg in transcripcion.segmentos:
            p_seg = doc.add_paragraph()
            p_seg.paragraph_format.space_after = Pt(3)
            tag = f"[{_segundos_a_tiempo(seg.inicio_s)} → {_segundos_a_tiempo(seg.fin_s)}] "
            r_tag = p_seg.add_run(tag)
            r_tag.bold = True
            r_tag.font.color.rgb = RGBColor(13, 110, 253)
            p_seg.add_run(seg.texto)

    buffer = io.BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    # Guardar en disco si se proporcionó ruta
    if ruta_salida is not None:
        ruta_p = Path(ruta_salida)
        ruta_p.parent.mkdir(parents=True, exist_ok=True)
        ruta_p.write_bytes(docx_bytes)

    return docx_bytes


def exportar_transcripcion_texto(transcripcion: Transcripcion) -> str:
    """Exporta la transcripción completa a texto plano formateado con marcas de tiempo."""
    minutos = int(transcripcion.duracion_s // 60)
    segundos = int(transcripcion.duracion_s % 60)
    lineas = [
        f"Transcripción Completa ({minutos:02d}:{segundos:02d})",
        f"Modelo: {transcripcion.modelo} · Segmentos: {len(transcripcion.segmentos)}",
        "=" * 60,
        "",
    ]
    for seg in transcripcion.segmentos:
        rango = f"[{_segundos_a_tiempo(seg.inicio_s)} → {_segundos_a_tiempo(seg.fin_s)}]"
        lineas.append(f"{rango} {seg.texto}")
    return "\n".join(lineas)

    buffer = io.BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    # Guardar en disco si se proporcionó ruta
    if ruta_salida is not None:
        ruta_p = Path(ruta_salida)
        ruta_p.parent.mkdir(parents=True, exist_ok=True)
        ruta_p.write_bytes(docx_bytes)

    return docx_bytes


# ==============================================================================
# 4. EXPORTACIÓN A EXCEL (.XLSX)
# ==============================================================================


def exportar_xlsx(
    resultado: ResultadoPonencia | ResultadoReunion | ResultadoEntrevista,
    ruta_salida: str | Path | None = None,
) -> bytes:
    """Genera un libro de Microsoft Excel (.xlsx) estructurado y estilizado.

    Crea hojas con formato:
    - Para Reunión: Hoja 'Tareas y Acuerdos' estilizada (ID, Tipo, Descripción,
      Responsable, Cita Literal, Inicio, Fin, Estado) y Hoja 'Resumen y Temas'.
    - Para Ponencia: Hoja 'Ideas Clave' y Hoja 'Preguntas y Resumen'.
    - Para Entrevista: Hoja 'Fragmentos Codificados' y Hoja 'Códigos temáticos'.

    Args:
        resultado: Estructuración de Ponencia, Reunión o Entrevista.
        ruta_salida: Ruta opcional donde guardar el archivo en disco.

    Returns:
        Bytes correspondientes al archivo binario .xlsx.
    """
    wb = openpyxl.Workbook()
    # Eliminar hoja por defecto al inicio
    wb.remove(wb.active)

    # Estilos compartidos
    fuente_encabezado = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    relleno_encabezado = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Azul marino
    fuente_datos = Font(name="Segoe UI", size=10)
    alineacion_encabezado = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alineacion_datos = Alignment(vertical="center", wrap_text=True)
    borde_fino = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    def _aplicar_estilo_fila(ws: Any, num_fila: int, es_header: bool = False) -> None:
        ws.row_dimensions[num_fila].height = 24 if es_header else 20
        for celda in ws[num_fila]:
            celda.border = borde_fino
            if es_header:
                celda.font = fuente_encabezado
                celda.fill = relleno_encabezado
                celda.alignment = alineacion_encabezado
            else:
                celda.font = fuente_datos
                celda.alignment = alineacion_datos

    def _autoajustar_columnas(ws: Any) -> None:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                # Considerar primera línea si tiene saltos de línea
                primera_linea = val_str.split("\n")[0]
                max_len = max(max_len, len(primera_linea))
            # Ajustar con límites razonables
            ancho_deseado = max(12, min(max_len + 3, 50))
            ws.column_dimensions[col_letter].width = ancho_deseado

    if isinstance(resultado, ResultadoReunion):
        # Hoja principal: 'Tareas y Acuerdos'
        ws_tareas = wb.create_sheet(title="Tareas y Acuerdos")
        encabezados_t = [
            "ID",
            "Tipo",
            "Descripción",
            "Responsable",
            "Fecha Límite",
            "Cita Literal",
            "Inicio",
            "Fin",
            "Estado",
        ]
        ws_tareas.append(encabezados_t)
        _aplicar_estilo_fila(ws_tareas, 1, es_header=True)

        contador = 1
        for t in resultado.tareas:
            ws_tareas.append([
                f"T-{contador:02d}",
                "Tarea",
                t.descripcion,
                t.responsable or "-",
                t.fecha_limite or "-",
                t.evidencia.cita,
                _segundos_a_tiempo(t.evidencia.inicio_s),
                "-",
                "Pendiente",
            ])
            contador += 1
            _aplicar_estilo_fila(ws_tareas, ws_tareas.max_row, es_header=False)

        contador_a = 1
        for a in resultado.acuerdos:
            ws_tareas.append([
                f"A-{contador_a:02d}",
                "Acuerdo",
                a.descripcion,
                "Todos",
                "-",
                a.evidencia.cita,
                _segundos_a_tiempo(a.evidencia.inicio_s),
                "-",
                "Pactado",
            ])
            contador_a += 1
            _aplicar_estilo_fila(ws_tareas, ws_tareas.max_row, es_header=False)

        _autoajustar_columnas(ws_tareas)

        # Hoja secundaria: 'Resumen y Temas'
        ws_temas = wb.create_sheet(title="Resumen y Temas")
        ws_temas.append(["Tema / Resumen", "Detalle", "Minuto", "Cita Literal"])
        _aplicar_estilo_fila(ws_temas, 1, es_header=True)

        ws_temas.append(["Resumen General", resultado.resumen_general, "-", "-"])
        _aplicar_estilo_fila(ws_temas, ws_temas.max_row, es_header=False)

        for tema in resultado.temas:
            primera_ev = tema.evidencias[0] if tema.evidencias else None
            ws_temas.append([
                tema.titulo,
                tema.resumen,
                _segundos_a_tiempo(primera_ev.inicio_s) if primera_ev else "-",
                primera_ev.cita if primera_ev else "-",
            ])
            _aplicar_estilo_fila(ws_temas, ws_temas.max_row, es_header=False)
        _autoajustar_columnas(ws_temas)

    elif isinstance(resultado, ResultadoPonencia):
        # Hoja 1: 'Ideas Clave'
        ws_ideas = wb.create_sheet(title="Ideas Clave")
        ws_ideas.append(["ID", "Título de Idea Clave", "Resumen", "Minuto", "Cita Literal"])
        _aplicar_estilo_fila(ws_ideas, 1, es_header=True)

        idx = 1
        for idea in resultado.ideas_clave:
            if idea.evidencias:
                for ev in idea.evidencias:
                    ws_ideas.append([
                        f"IC-{idx:02d}",
                        idea.titulo,
                        idea.resumen,
                        _segundos_a_tiempo(ev.inicio_s),
                        ev.cita,
                    ])
                    idx += 1
                    _aplicar_estilo_fila(ws_ideas, ws_ideas.max_row, es_header=False)
            else:
                ws_ideas.append([
                    f"IC-{idx:02d}",
                    idea.titulo,
                    idea.resumen,
                    "-",
                    "-",
                ])
                idx += 1
                _aplicar_estilo_fila(ws_ideas, ws_ideas.max_row, es_header=False)
        _autoajustar_columnas(ws_ideas)

        # Hoja 2: 'Preguntas y Resumen'
        ws_resumen = wb.create_sheet(title="Preguntas y Resumen")
        ws_resumen.append(["Tipo", "Descripción", "Minuto", "Cita Literal"])
        _aplicar_estilo_fila(ws_resumen, 1, es_header=True)

        ws_resumen.append(["Resumen General", resultado.resumen_general, "-", "-"])
        _aplicar_estilo_fila(ws_resumen, ws_resumen.max_row, es_header=False)

        for p in resultado.preguntas:
            ws_resumen.append([
                "Pregunta",
                p.descripcion,
                _segundos_a_tiempo(p.evidencia.inicio_s),
                p.evidencia.cita,
            ])
            _aplicar_estilo_fila(ws_resumen, ws_resumen.max_row, es_header=False)
        _autoajustar_columnas(ws_resumen)

    elif isinstance(resultado, ResultadoEntrevista):
        # Hoja 1: 'Fragmentos Codificados'
        ws_frag = wb.create_sheet(title="Fragmentos Codificados")
        ws_frag.append(["ID", "Código", "Minuto", "Cita Literal", "Nota Analítica"])
        _aplicar_estilo_fila(ws_frag, 1, es_header=True)

        for i, f in enumerate(resultado.fragmentos, 1):
            ws_frag.append([
                f"F-{i:02d}",
                f.codigo,
                _segundos_a_tiempo(f.evidencia.inicio_s),
                f.evidencia.cita,
                f.nota or "-",
            ])
            _aplicar_estilo_fila(ws_frag, ws_frag.max_row, es_header=False)
        _autoajustar_columnas(ws_frag)

        # Hoja 2: 'Códigos temáticos'
        ws_libro = wb.create_sheet(title="Códigos temáticos")
        ws_libro.append(["Código", "Descripción", "Resumen Sintetizado"])
        _aplicar_estilo_fila(ws_libro, 1, es_header=True)

        for c in resultado.libro:
            res_c = resultado.resumen_por_codigo.get(c.codigo, "-")
            ws_libro.append([c.codigo, c.descripcion, res_c])
            _aplicar_estilo_fila(ws_libro, ws_libro.max_row, es_header=False)
        _autoajustar_columnas(ws_libro)

    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_bytes = buffer.getvalue()

    if ruta_salida is not None:
        ruta_p = Path(ruta_salida)
        ruta_p.parent.mkdir(parents=True, exist_ok=True)
        ruta_p.write_bytes(xlsx_bytes)

    return xlsx_bytes
