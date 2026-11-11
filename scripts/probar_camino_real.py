"""Script para ejecutar la prueba real del camino real (T70).

Carga data/fixtures/transcripcion_ponencia.json con la plantilla Clase (ponencia),
invoca a la API de Gemini (temperatura 0.0, thinking low), y comprueba que:
1. El mapa mental tiene al menos 3 ramas.
2. Hay 0 citas descartadas.
Imprime latencia, modelo que respondió, usageMetadata y títulos de las ramas.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from minuta.esquemas import Transcripcion
from minuta.estructurar import estructurar_transcripcion
from minuta.proveedores import ProveedorGemini


def ejecutar_camino_real() -> int:
    ruta_fixture = ROOT_DIR / "data" / "fixtures" / "transcripcion_ponencia.json"
    if not ruta_fixture.exists():
        print(f"Error: Fixture no encontrado en {ruta_fixture}", file=sys.stderr)
        return 1

    datos = json.loads(ruta_fixture.read_text(encoding="utf-8"))
    transcripcion = Transcripcion.model_validate(datos)

    proveedor = ProveedorGemini()

    print("======================================================================")
    print("EJECUTANDO PRUEBA REAL DEL CAMINO REAL (T70)")
    print(f"Fixture: {ruta_fixture.name} ({transcripcion.duracion_s} s, {len(transcripcion.segmentos)} segs)")
    print(f"Plantilla: Ponencia / Clase (ponencia) | Proveedor: Gemini ({proveedor.modelo})")
    print("======================================================================")

    t0 = time.perf_counter()
    resultado = estructurar_transcripcion(
        transcripcion=transcripcion,
        tipo_plantilla="ponencia",
        proveedor=proveedor,
        modo="solo_llm",
    )
    latencia_s = time.perf_counter() - t0

    num_ramas = len(resultado.mapa.raiz.hijos) if (resultado.mapa and resultado.mapa.raiz) else 0
    titulos_ramas = [h.titulo for h in resultado.mapa.raiz.hijos] if num_ramas else []
    descartados = resultado.descartados
    modelo_respondio = proveedor.ultimo_modelo
    uso = proveedor.ultimo_uso or {}

    print(f"Latencia: {latencia_s:.2f} s")
    print(f"Modelo que respondió: {modelo_respondio}")
    print(f"Uso de tokens: {uso}")
    print(f"Citas descartadas: {descartados}")
    print(f"Número de ramas en el mapa: {num_ramas}")
    print("Títulos de las ramas:")
    for i, t in enumerate(titulos_ramas, start=1):
        print(f"  {i}. {t}")
    print("======================================================================")

    errores: list[str] = []
    if num_ramas < 3:
        errores.append(f"Se esperaban al menos 3 ramas en el mapa mental, se obtuvieron {num_ramas}")
    if descartados != 0:
        errores.append(f"Se esperaban 0 citas descartadas, se obtuvieron {descartados}")

    if errores:
        print("VEREDICTO: FALLO")
        for e in errores:
            print(f"  - {e}")
        return 1

    print("VEREDICTO: ÉXITO (camino real validado)")
    return 0


if __name__ == "__main__":
    sys.exit(ejecutar_camino_real())
