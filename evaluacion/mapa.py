"""Arnés de evaluación para mapas mentales interactivos (evaluacion/mapa.py).

Evalúa la hipótesis pre-registrada H9 de Minuta:
"El mapa mental es verificable y útil:
Confirmada si: >= 90% de nodos (sin contar la raíz) tienen cita literal verificada,
2 a 4 niveles de profundidad y 4 a 8 ramas principales en 1 hora.
Falsada si: < 75% con cita o no cumple con evidencia literal.
No concluyente en caso intermedio."
"""

from __future__ import annotations

import argparse
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from minuta.esquemas import Evidencia, MapaMental, NodoMapa, Segmento, validar_evidencia_literal

# Umbrales pre-registrados para la hipótesis H9
UMBRAL_CITAS_MAPA_CONFIRMADA: float = 90.0
UMBRAL_CITAS_MAPA_FALSADA: float = 75.0
PROFUNDIDAD_MIN_CONFIRMADA: int = 2
PROFUNDIDAD_MAX_CONFIRMADA: int = 4
RAMAS_MIN_CONFIRMADA: int = 4
RAMAS_MAX_CONFIRMADA: int = 8


class VeredictoH9(str, Enum):
    """Veredicto formal de la hipótesis H9 bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


def analizar_estructura_mapa(
    mapa: MapaMental | NodoMapa | dict[str, Any],
    segmentos: Sequence[Segmento | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analiza recursivamente el árbol del mapa mental calculando profundidad, ramas y citas."""
    # Extraer nodo raíz
    if isinstance(mapa, MapaMental):
        raiz = mapa.raiz
    elif isinstance(mapa, NodoMapa):
        raiz = mapa
    elif isinstance(mapa, dict):
        if "mapa" in mapa and isinstance(mapa["mapa"], dict):
            raiz_dict = mapa["mapa"].get("raiz", mapa["mapa"])
        elif "raiz" in mapa and isinstance(mapa["raiz"], dict):
            raiz_dict = mapa["raiz"]
        else:
            raiz_dict = mapa
        raiz = NodoMapa.model_validate(raiz_dict)
    else:
        raise TypeError(f"Tipo no soportado para mapa: {type(mapa)}")

    # Convertir segmentos a objetos Segmento si se suministran
    segs_obj: list[Segmento] = []
    if segmentos:
        for s in segmentos:
            if isinstance(s, Segmento):
                segs_obj.append(s)
            elif isinstance(s, dict):
                segs_obj.append(Segmento(id=s["id"], inicio_s=s["inicio_s"], fin_s=s["fin_s"], texto=s["texto"]))

    total_nodos_sin_raiz = 0
    nodos_con_cita = 0
    citas_literales_validadas = 0
    nodos_por_nivel: dict[int, int] = {}
    detalles_nodos: list[dict[str, Any]] = []

    def _recorrer(nodo: NodoMapa, nivel: int) -> int:
        nonlocal total_nodos_sin_raiz, nodos_con_cita, citas_literales_validadas

        nodos_por_nivel[nivel] = nodos_por_nivel.get(nivel, 0) + 1
        prof_max = nivel

        if nivel > 1:
            total_nodos_sin_raiz += 1
            tiene_cita = False
            es_literal = False

            if nodo.evidencia is not None and nodo.evidencia.cita and nodo.evidencia.cita.strip():
                tiene_cita = True
                nodos_con_cita += 1
                # Sin segmentos no hay contra qué cotejar: la cita no cuenta como literal
                if segs_obj:
                    es_literal = validar_evidencia_literal(nodo.evidencia.cita, segs_obj)
                    if es_literal:
                        citas_literales_validadas += 1

            detalles_nodos.append({
                "id": nodo.id,
                "titulo": nodo.titulo,
                "nivel": nivel,
                "tiene_cita": tiene_cita,
                "es_literal": es_literal,
                "cita": nodo.evidencia.cita if (nodo.evidencia and tiene_cita) else None,
            })

        for hijo in nodo.hijos:
            sub_prof = _recorrer(hijo, nivel + 1)
            if sub_prof > prof_max:
                prof_max = sub_prof

        return prof_max

    profundidad_maxima = _recorrer(raiz, 1)
    ramas_principales = len(raiz.hijos)

    pct_nodos_con_cita = (
        (nodos_con_cita / total_nodos_sin_raiz * 100.0) if total_nodos_sin_raiz > 0 else 0.0
    )
    pct_citas_literales = (
        (citas_literales_validadas / total_nodos_sin_raiz * 100.0) if total_nodos_sin_raiz > 0 else 0.0
    )

    return {
        "titulo": getattr(mapa, "titulo", raiz.titulo),
        "total_nodos_sin_raiz": total_nodos_sin_raiz,
        "nodos_con_cita": nodos_con_cita,
        "pct_nodos_con_cita": pct_nodos_con_cita,
        "citas_literales_validadas": citas_literales_validadas,
        "pct_citas_literales": pct_citas_literales,
        "profundidad_maxima": profundidad_maxima,
        "ramas_principales": ramas_principales,
        "nodos_por_nivel": nodos_por_nivel,
        "detalles": detalles_nodos,
    }


def evaluar_hipotesis_h9(
    pct_citas_literales: float,
    profundidad: int,
    ramas_principales: int,
) -> dict[str, Any]:
    """Aplica la regla de decisión formal HDD para la hipótesis H9.

    Decide con el porcentaje de nodos (sin la raíz) cuya cita es literal según la
    transcripción, no con el porcentaje de nodos que simplemente traen una cita.
    """
    if pct_citas_literales < UMBRAL_CITAS_MAPA_FALSADA:
        veredicto = VeredictoH9.FALSADA
        motivo = (
            f"Falsada: Porcentaje de nodos con cita literal ({pct_citas_literales:.1f}%) < "
            f"{UMBRAL_CITAS_MAPA_FALSADA:.0f}%."
        )
    elif (
        pct_citas_literales >= UMBRAL_CITAS_MAPA_CONFIRMADA
        and PROFUNDIDAD_MIN_CONFIRMADA <= profundidad <= PROFUNDIDAD_MAX_CONFIRMADA
        and RAMAS_MIN_CONFIRMADA <= ramas_principales <= RAMAS_MAX_CONFIRMADA
    ):
        veredicto = VeredictoH9.CONFIRMADA
        motivo = (
            f"Confirmada: Citas literales ({pct_citas_literales:.1f}%) >= {UMBRAL_CITAS_MAPA_CONFIRMADA:.0f}%, "
            f"profundidad ({profundidad}) en [{PROFUNDIDAD_MIN_CONFIRMADA}, {PROFUNDIDAD_MAX_CONFIRMADA}] "
            f"y ramas principales ({ramas_principales}) en [{RAMAS_MIN_CONFIRMADA}, {RAMAS_MAX_CONFIRMADA}]."
        )
    else:
        veredicto = VeredictoH9.NO_CONCLUYENTE
        motivo = (
            f"No concluyente: Citas literales ({pct_citas_literales:.1f}%), profundidad ({profundidad}) "
            f"o ramas ({ramas_principales}) se ubican en zona intermedia o fuera del rango ideal de 1 hora."
        )

    return {
        "pct_citas_literales": pct_citas_literales,
        "profundidad": profundidad,
        "ramas_principales": ramas_principales,
        "veredicto": veredicto,
        "motivo": motivo,
    }


def evaluar_mapa_archivo(
    ruta_pred: str | Path,
    ruta_transcripcion: str | Path | None = None,
) -> dict[str, Any]:
    """Evalúa el mapa mental cargándolo de un archivo JSON estructurado.

    La transcripción es obligatoria: sin ella no se puede comprobar que las citas
    sean literales, y H9 decide justamente con ese porcentaje.
    """
    p_pred = Path(ruta_pred)
    if not p_pred.exists():
        raise FileNotFoundError(f"Archivo de mapa no encontrado: {p_pred}")

    if not ruta_transcripcion:
        raise ValueError(
            "H9 requiere la transcripción (--transcripcion) para cotejar que las citas sean literales."
        )
    p_trans = Path(ruta_transcripcion)
    if not p_trans.exists():
        raise FileNotFoundError(f"Archivo de transcripción no encontrado: {p_trans}")

    with open(p_pred, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(p_trans, "r", encoding="utf-8") as f:
        d_trans = json.load(f)
    segmentos = d_trans.get("segmentos", []) if isinstance(d_trans, dict) else []
    if not segmentos:
        raise ValueError(f"La transcripción no tiene segmentos con los que cotejar las citas: {p_trans}")

    stats = analizar_estructura_mapa(data, segmentos=segmentos)
    eval_h9 = evaluar_hipotesis_h9(
        pct_citas_literales=stats["pct_citas_literales"],
        profundidad=stats["profundidad_maxima"],
        ramas_principales=stats["ramas_principales"],
    )

    return {
        "ruta_pred": str(p_pred),
        "ruta_transcripcion": str(p_trans),
        "stats": stats,
        "evaluacion_h9": eval_h9,
    }


def imprimir_reporte_mapa(resultado: dict[str, Any]) -> None:
    """Imprime el reporte en consola formateado para evaluación H9."""
    stats = resultado["stats"]
    eval_h9 = resultado["evaluacion_h9"]

    print("=" * 72)
    print("EVALUACIÓN DE MAPA MENTAL JERÁRQUICO - HIPÓTESIS H9")
    print("=" * 72)
    print(f"Archivo analizado   : {resultado.get('ruta_pred', 'N/A')}")
    print(f"Transcripción       : {resultado.get('ruta_transcripcion', 'N/A')}")
    print(f"Título del mapa     : {stats['titulo']}")
    print("-" * 72)
    print("Métricas Estructurales:")
    print(f"  Total nodos (sin raíz)      : {stats['total_nodos_sin_raiz']}")
    print(f"  Ramas principales (nivel 2) : {stats['ramas_principales']} (rango ideal: {RAMAS_MIN_CONFIRMADA}–{RAMAS_MAX_CONFIRMADA})")
    print(f"  Profundidad máxima          : {stats['profundidad_maxima']} niveles (rango ideal: {PROFUNDIDAD_MIN_CONFIRMADA}–{PROFUNDIDAD_MAX_CONFIRMADA})")
    print(f"  Nodos con cita de evidencia : {stats['nodos_con_cita']} / {stats['total_nodos_sin_raiz']} ({stats['pct_nodos_con_cita']:.2f} %)")
    print(f"  Citas literales validadas   : {stats['citas_literales_validadas']} / {stats['total_nodos_sin_raiz']}")
    print(f"  Porcentaje de citas literales: {stats['pct_citas_literales']:.2f} % (umbral >= {UMBRAL_CITAS_MAPA_CONFIRMADA:.0f}%)")
    print("-" * 72)
    print("Distribución por Nivel:")
    for niv, cnt in sorted(stats["nodos_por_nivel"].items()):
        print(f"  Nivel {niv}: {cnt} nodos")
    print("=" * 72)
    print("Veredicto de Hipótesis H9:")
    print(f"  VEREDICTO : {eval_h9['veredicto'].value}")
    print(f"  Detalle   : {eval_h9['motivo']}")
    print("=" * 72)


def main() -> None:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Evaluación de calidad y verificabilidad de mapa mental (H9)")
    parser.add_argument("--pred", type=str, required=True, help="Ruta al JSON estructurado con árbol de mapa mental")
    parser.add_argument(
        "--transcripcion",
        type=str,
        required=True,
        help="Ruta al JSON de transcripción (obligatoria: H9 decide con el %% de citas literales cotejadas)",
    )

    args = parser.parse_args()

    try:
        res = evaluar_mapa_archivo(
            ruta_pred=args.pred,
            ruta_transcripcion=args.transcripcion,
        )
        imprimir_reporte_mapa(res)
    except Exception as exc:
        print(f"ERROR en evaluacion.mapa: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
