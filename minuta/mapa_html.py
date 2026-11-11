"""Generador de componentes HTML para visualización interactiva de mapas mentales con Markmap.

Utiliza markmap-autoloader con una versión de CDN fija (0.17.2), optimizado para
dispositivos móviles y compatible con Streamlit (components.v1.html).
"""

from __future__ import annotations

from minuta.esquemas import MapaMental

VERSION_MARKMAP_CDN = "0.17.2"


def generar_componente_markmap(mapa: MapaMental, altura_px: int = 450) -> str:
    """Genera un fragmento HTML autónomo y responsivo para incrustar el mapa mental.

    Diseñado para Streamlit components.v1.html o navegadores móviles y de escritorio.

    Args:
        mapa: Instancia de MapaMental con la jerarquía de nodos.
        altura_px: Altura en píxeles del contenedor interactivo.

    Returns:
        Cadena con el código HTML/CSS/JS completo listo para renderizar.
    """
    markdown_arbol = mapa.to_markdown()
    # Escapar cierre de script para evitar inyecciones o rupturas del bloque template
    markdown_seguro = markdown_arbol.replace("</script>", "<\\/script>")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=3.0, user-scalable=yes">
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
      touch-action: pan-x pan-y pinch-zoom;
    }}
    .markmap-container {{
      position: relative;
      width: 100%;
      height: {altura_px}px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fafbfc;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
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
      color: #64748b;
      background: rgba(255, 255, 255, 0.90);
      border: 1px solid #cbd5e1;
      padding: 3px 8px;
      border-radius: 4px;
      pointer-events: none;
      user-select: none;
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
    <div class="markmap-help">📱 Pellizca para zoom · Arrastra para explorar</div>
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
