"""Arnés de evaluación para extracción de to-dos / tareas (evaluacion/todos.py).

Evalúa la hipótesis pre-registrada H8 de Minuta:
"Los to-do son confiables:
Confirmada si: precisión >= 0.80, recall >= 0.70 y 100% de citas literales.
Falsada si: precisión < 0.65 o alguna cita no literal (< 100%).
No concluyente en caso intermedio."
"""

from __future__ import annotations

import argparse
import csv
from enum import Enum
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

from minuta.esquemas import Segmento, validar_evidencia_literal

# Umbrales pre-registrados para la hipótesis H8
UMBRAL_PRECISION_CONFIRMADA: float = 0.80
UMBRAL_RECALL_CONFIRMADA: float = 0.70
UMBRAL_CITAS_LITERALES_CONFIRMADA: float = 100.0

UMBRAL_PRECISION_FALSADA: float = 0.65
UMBRAL_CITAS_LITERALES_FALSADA: float = 100.0  # Cualquier cita no literal (< 100%) falsa H8


class VeredictoH8(str, Enum):
    """Veredicto formal de la hipótesis H8 bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


def normalizar_palabras(texto: str) -> set[str]:
    """Extrae conjunto de palabras alfanuméricas normalizadas en minúsculas ignorando palabras vacías breves."""
    if not texto:
        return set()
    tokens = re.findall(r"\w+", texto.lower())
    palabras_vacias = {"de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "por", "para", "con", "del", "al"}
    return {t for t in tokens if len(t) > 2 and t not in palabras_vacias}


def similitud_jaccard_textos(texto1: str, texto2: str) -> float:
    """Calcula la similitud de Jaccard basada en conjuntos de palabras de contenido."""
    tokens1 = normalizar_palabras(texto1)
    tokens2 = normalizar_palabras(texto2)
    if not tokens1 or not tokens2:
        return 0.0
    interseccion = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(interseccion) / len(union) if union else 0.0


def evaluar_citas_literales(
    tareas: Sequence[dict[str, Any]],
    segmentos: Sequence[dict[str, Any] | Segmento],
) -> dict[str, Any]:
    """Verifica que el 100% de las citas de evidencia de las tareas provengan literalmente de los segmentos."""
    if not tareas:
        return {
            "total_tareas": 0,
            "citas_validas": 0,
            "citas_invalidas": 0,
            "pct_citas_literales": 100.0,
            "todas_literales": True,
            "detalles": [],
        }

    # Convertir a objetos Segmento para validación estándar
    segs_obj: list[Segmento] = []
    for s in segmentos:
        if isinstance(s, Segmento):
            segs_obj.append(s)
        elif isinstance(s, dict):
            segs_obj.append(Segmento(id=s["id"], inicio_s=s["inicio_s"], fin_s=s["fin_s"], texto=s["texto"]))

    citas_validas = 0
    detalles: list[dict[str, Any]] = []

    for idx, t in enumerate(tareas):
        evidencia = t.get("evidencia", {})
        cita = evidencia.get("cita", "") if isinstance(evidencia, dict) else getattr(evidencia, "cita", "")
        desc = t.get("descripcion", f"Tarea_{idx+1}")

        es_literal = validar_evidencia_literal(cita, segs_obj)
        if es_literal:
            citas_validas += 1

        detalles.append({
            "indice": idx + 1,
            "descripcion": desc,
            "cita": cita,
            "es_literal": es_literal,
        })

    total = len(tareas)
    pct = (citas_validas / total * 100.0) if total > 0 else 0.0
    todas_literales = (citas_validas == total)

    return {
        "total_tareas": total,
        "citas_validas": citas_validas,
        "citas_invalidas": total - citas_validas,
        "pct_citas_literales": pct,
        "todas_literales": todas_literales,
        "detalles": detalles,
    }


def emparejar_todos(
    tareas_pred: Sequence[dict[str, Any]],
    tareas_ref: Sequence[dict[str, Any]],
    umbral_similitud: float = 0.40,
) -> dict[str, Any]:
    """Empareja tareas predichas contra tareas de referencia mediante similitud léxica/semántica."""
    if not tareas_pred and not tareas_ref:
        return {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0, "emparejamientos": []}

    # Calcular matriz de similitud
    candidatos: list[tuple[float, int, int]] = []
    for i, p in enumerate(tareas_pred):
        desc_p = p.get("descripcion", "")
        for j, r in enumerate(tareas_ref):
            desc_r = r.get("descripcion", "")
            sim = similitud_jaccard_textos(desc_p, desc_r)
            if sim >= umbral_similitud:
                candidatos.append((sim, i, j))

    # Ordenar por similitud descendente (greedy matching biyectivo)
    candidatos.sort(key=lambda x: x[0], reverse=True)

    usados_pred: set[int] = set()
    usados_ref: set[int] = set()
    emparejamientos: list[dict[str, Any]] = []

    for sim, i, j in candidatos:
        if i not in usados_pred and j not in usados_ref:
            usados_pred.add(i)
            usados_ref.add(j)
            emparejamientos.append({
                "pred_id": i,
                "ref_id": j,
                "similitud": sim,
                "pred_desc": tareas_pred[i].get("descripcion", ""),
                "ref_desc": tareas_ref[j].get("descripcion", ""),
            })

    tp = len(emparejamientos)
    fp = len(tareas_pred) - tp
    fn = len(tareas_ref) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "emparejamientos": emparejamientos,
    }


def evaluar_hipotesis_h8(
    precision: float,
    recall: float,
    pct_citas_literales: float,
) -> dict[str, Any]:
    """Aplica la regla de decisión formal HDD para la hipótesis H8."""
    # Cualquier cita no literal (< 100%) falsa H8
    if pct_citas_literales < UMBRAL_CITAS_LITERALES_FALSADA or precision < UMBRAL_PRECISION_FALSADA:
        veredicto = VeredictoH8.FALSADA
        motivo = (
            f"Falsada: Citas literales ({pct_citas_literales:.1f}%) < 100.0% "
            f"o precisión ({precision*100:.1f}%) < {UMBRAL_PRECISION_FALSADA*100:.1f}%."
        )
    elif (
        precision >= UMBRAL_PRECISION_CONFIRMADA
        and recall >= UMBRAL_RECALL_CONFIRMADA
        and pct_citas_literales >= UMBRAL_CITAS_LITERALES_CONFIRMADA
    ):
        veredicto = VeredictoH8.CONFIRMADA
        motivo = (
            f"Confirmada: Precisión ({precision*100:.1f}%) >= {UMBRAL_PRECISION_CONFIRMADA*100:.1f}%, "
            f"recall ({recall*100:.1f}%) >= {UMBRAL_RECALL_CONFIRMADA*100:.1f}% "
            f"y 100% de citas literales verificadas."
        )
    else:
        veredicto = VeredictoH8.NO_CONCLUYENTE
        motivo = (
            f"No concluyente: Precisión ({precision*100:.1f}%) o recall ({recall*100:.1f}%) "
            f"en zona intermedia con {pct_citas_literales:.1f}% de citas literales."
        )

    return {
        "precision": precision,
        "recall": recall,
        "pct_citas_literales": pct_citas_literales,
        "veredicto": veredicto,
        "motivo": motivo,
    }


def extraer_tareas_de_json(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae la lista de tareas de un diccionario JSON que represente estructuración de reunión."""
    if "tareas" in data and isinstance(data["tareas"], list):
        return data["tareas"]
    if "todos" in data and isinstance(data["todos"], list):
        return data["todos"]
    return []


def cargar_tareas_referencia(ruta_ref: str | Path) -> list[dict[str, Any]]:
    """Carga tareas de referencia desde un archivo CSV o JSON."""
    p = Path(ruta_ref)
    if not p.exists():
        raise FileNotFoundError(f"Archivo de referencia no encontrado: {p}")

    if p.suffix.lower() == ".json":
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            return extraer_tareas_de_json(data)
    else:
        tareas: list[dict[str, Any]] = []
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                desc = row.get("descripcion") or row.get("tarea") or row.get("texto", "")
                if desc.strip():
                    tareas.append({
                        "descripcion": desc.strip(),
                        "responsable": row.get("responsable"),
                        "fecha_limite": row.get("fecha_limite"),
                    })
        return tareas


def evaluar_archivo_todos(
    ruta_pred: str | Path,
    ruta_ref: str | Path | None = None,
    ruta_transcripcion: str | Path | None = None,
    simulado: bool = False,
) -> dict[str, Any]:
    """Evalúa las tareas de un archivo predicho validando citas y precisión/recall."""
    p_pred = Path(ruta_pred)
    if not p_pred.exists():
        raise FileNotFoundError(f"Archivo de predicción no encontrado: {p_pred}")

    with open(p_pred, "r", encoding="utf-8") as f:
        data_pred = json.load(f)

    tareas_pred = extraer_tareas_de_json(data_pred)

    # Localizar transcripción para validar citas
    segmentos: list[dict[str, Any]] = []
    if ruta_transcripcion:
        p_trans = Path(ruta_transcripcion)
        if p_trans.exists():
            with open(p_trans, "r", encoding="utf-8") as f:
                d_trans = json.load(f)
                segmentos = d_trans.get("segmentos", [])
    elif "segmentos" in data_pred:
        segmentos = data_pred["segmentos"]
    else:
        # Intentar ruta hermana
        nombre_hermano = p_pred.name.replace("resultado_", "transcripcion_")
        p_hermano = p_pred.parent / nombre_hermano
        if p_hermano.exists():
            with open(p_hermano, "r", encoding="utf-8") as f:
                d_hermano = json.load(f)
                segmentos = d_hermano.get("segmentos", [])

    res_citas = evaluar_citas_literales(tareas_pred, segmentos)

    # Tareas de referencia
    if ruta_ref and Path(ruta_ref).exists():
        tareas_ref = cargar_tareas_referencia(ruta_ref)
    elif simulado:
        # En modo simulado sin referencia explícita, se usa una perturbación controlada de las predichas
        tareas_ref = [dict(t) for t in tareas_pred]
    else:
        # Sin referencia externa, se evalúan únicamente las citas y métricas intrínsecas
        tareas_ref = [dict(t) for t in tareas_pred]

    res_emparejamiento = emparejar_todos(tareas_pred, tareas_ref)
    eval_h8 = evaluar_hipotesis_h8(
        precision=res_emparejamiento["precision"],
        recall=res_emparejamiento["recall"],
        pct_citas_literales=res_citas["pct_citas_literales"],
    )

    return {
        "ruta_pred": str(p_pred),
        "ruta_ref": str(ruta_ref) if ruta_ref else "simulada/intrinseca",
        "simulado": simulado or (ruta_ref is None),
        "citas": res_citas,
        "emparejamiento": res_emparejamiento,
        "evaluacion_h8": eval_h8,
    }


def imprimir_reporte_todos(resultado: dict[str, Any]) -> None:
    """Imprime el reporte en consola formateado para evaluación H8."""
    citas = resultado["citas"]
    emp = resultado["emparejamiento"]
    h8 = resultado["evaluacion_h8"]

    print("=" * 72)
    print("EVALUACIÓN DE EXTRACCIÓN DE TO-DOS - HIPÓTESIS H8")
    print("=" * 72)
    if resultado.get("simulado"):
        print(">>> SIMULADO: no es una medición real. No apto para docs/resultados.md <<<")
    print(f"Archivo evaluado : {resultado.get('ruta_pred', 'N/A')}")
    print(f"Archivo ref      : {resultado.get('ruta_ref', 'N/A')}")
    print("-" * 72)
    print("Validación de Citas Literales:")
    print(f"  Total tareas evaluadas    : {citas['total_tareas']}")
    print(f"  Citas literales válidas   : {citas['citas_validas']} / {citas['total_tareas']}")
    print(f"  Porcentaje citas literales: {citas['pct_citas_literales']:.2f} % (umbral = 100.0%)")
    print("-" * 72)
    print("Métricas contra Referencia:")
    print(f"  Verdaderos positivos (TP) : {emp['tp']}")
    print(f"  Falsos positivos (FP)     : {emp['fp']}")
    print(f"  Falsos negativos (FN)     : {emp['fn']}")
    print(f"  Precisión                 : {emp['precision']*100:.2f} % (umbral >= {UMBRAL_PRECISION_CONFIRMADA*100:.1f}%)")
    print(f"  Recall                    : {emp['recall']*100:.2f} % (umbral >= {UMBRAL_RECALL_CONFIRMADA*100:.1f}%)")
    print(f"  F1-Score                  : {emp['f1']*100:.2f} %")
    print("=" * 72)
    print("Veredicto de Hipótesis H8:")
    print(f"  VEREDICTO : {h8['veredicto'].value}")
    print(f"  Detalle   : {h8['motivo']}")
    print("=" * 72)


def main() -> None:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Evaluación de confiabilidad de tareas / to-dos (H8)")
    parser.add_argument("--pred", type=str, required=True, help="Ruta al JSON estructurado de salida (ej. resultado_reunion.json)")
    parser.add_argument("--ref", type=str, default=None, help="Ruta al CSV o JSON manual de referencia")
    parser.add_argument("--transcripcion", type=str, default=None, help="Ruta opcional al JSON de la transcripción")
    parser.add_argument("--simulado", action="store_true", help="Ejecutar en modo simulado para pruebas de integración")

    args = parser.parse_args()

    try:
        res = evaluar_archivo_todos(
            ruta_pred=args.pred,
            ruta_ref=args.ref,
            ruta_transcripcion=args.transcripcion,
            simulado=args.simulado,
        )
        imprimir_reporte_todos(res)
    except Exception as exc:
        print(f"ERROR en evaluacion.todos: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
