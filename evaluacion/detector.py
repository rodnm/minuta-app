"""Arnés de evaluación para el detector multiclase de segmentos (evaluacion/detector.py).

Evalúa la hipótesis pre-registrada H4 de Minuta:
"mmBERT-small afinado con datos sintéticos generaliza:
Confirmada si: F1 macro >= 0.70 y recall de 'tarea' >= 0.80 en la reunión actuada etiquetada a mano.
Falsada si: F1 macro < 0.55 o recall de 'tarea' < 0.65.
No concluyente en caso intermedio."
"""

from __future__ import annotations

import argparse
import csv
from enum import Enum
import json
from pathlib import Path
import random
import sys
from typing import Any, Sequence

# Clases del detector en orden estándar
CLASES_DETECTOR: tuple[str, ...] = ("idea", "tarea", "acuerdo", "pregunta", "relleno")

# Umbrales pre-registrados para la hipótesis H4
UMBRAL_F1_CONFIRMADA: float = 0.70
UMBRAL_RECALL_TAREA_CONFIRMADA: float = 0.80
UMBRAL_F1_FALSADA: float = 0.55
UMBRAL_RECALL_TAREA_FALSADA: float = 0.65


class VeredictoH4(str, Enum):
    """Veredicto formal de la hipótesis H4 bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


def calcular_metricas_clasificacion(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    clases: Sequence[str] = CLASES_DETECTOR,
) -> dict[str, Any]:
    """Calcula métricas de clasificación multiclase (precisión, recall, f1, soporte) por clase y macro."""
    if len(y_true) != len(y_pred):
        raise ValueError(f"Longitudes dispares entre y_true ({len(y_true)}) y y_pred ({len(y_pred)})")

    total_muestras = len(y_true)
    if total_muestras == 0:
        return {
            "total_muestras": 0,
            "accuracy": 0.0,
            "f1_macro": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "por_clase": {c: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0} for c in clases},
        }

    # Conteos de Verdaderos Positivos (TP), Falsos Positivos (FP), Falsos Negativos (FN) y soporte
    tp = {c: 0 for c in clases}
    fp = {c: 0 for c in clases}
    fn = {c: 0 for c in clases}
    soporte = {c: 0 for c in clases}
    aciertos_globales = 0

    for true_lbl, pred_lbl in zip(y_true, y_pred):
        if true_lbl in soporte:
            soporte[true_lbl] += 1
        if true_lbl == pred_lbl:
            aciertos_globales += 1
            if pred_lbl in tp:
                tp[pred_lbl] += 1
        else:
            if pred_lbl in fp:
                fp[pred_lbl] += 1
            if true_lbl in fn:
                fn[true_lbl] += 1

    metricas_clase: dict[str, dict[str, float | int]] = {}
    f1_acumulado = 0.0
    prec_acumulada = 0.0
    rec_acumulado = 0.0

    for c in clases:
        c_tp = tp[c]
        c_fp = fp[c]
        c_fn = fn[c]
        c_soporte = soporte[c]

        prec = (c_tp / (c_tp + c_fp)) if (c_tp + c_fp) > 0 else 0.0
        rec = (c_tp / (c_tp + c_fn)) if (c_tp + c_fn) > 0 else 0.0
        f1 = (2.0 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        metricas_clase[c] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "support": c_soporte,
        }

        prec_acumulada += prec
        rec_acumulado += rec
        f1_acumulado += f1

    num_clases = len(clases)
    f1_macro = f1_acumulado / num_clases if num_clases > 0 else 0.0
    prec_macro = prec_acumulada / num_clases if num_clases > 0 else 0.0
    rec_macro = rec_acumulado / num_clases if num_clases > 0 else 0.0
    accuracy = aciertos_globales / total_muestras if total_muestras > 0 else 0.0

    return {
        "total_muestras": total_muestras,
        "accuracy": accuracy,
        "f1_macro": f1_macro,
        "precision_macro": prec_macro,
        "recall_macro": rec_macro,
        "por_clase": metricas_clase,
    }


def evaluar_hipotesis_h4(f1_macro: float, recall_tarea: float) -> dict[str, Any]:
    """Aplica la regla de decisión formal HDD para la hipótesis H4."""
    if f1_macro < UMBRAL_F1_FALSADA or recall_tarea < UMBRAL_RECALL_TAREA_FALSADA:
        veredicto = VeredictoH4.FALSADA
        motivo = (
            f"Falsada: F1 macro ({f1_macro:.3f}) < {UMBRAL_F1_FALSADA:.2f} "
            f"o recall de tarea ({recall_tarea:.3f}) < {UMBRAL_RECALL_TAREA_FALSADA:.2f}."
        )
    elif f1_macro >= UMBRAL_F1_CONFIRMADA and recall_tarea >= UMBRAL_RECALL_TAREA_CONFIRMADA:
        veredicto = VeredictoH4.CONFIRMADA
        motivo = (
            f"Confirmada: F1 macro ({f1_macro:.3f}) >= {UMBRAL_F1_CONFIRMADA:.2f} "
            f"y recall de tarea ({recall_tarea:.3f}) >= {UMBRAL_RECALL_TAREA_CONFIRMADA:.2f}."
        )
    else:
        veredicto = VeredictoH4.NO_CONCLUYENTE
        motivo = (
            f"No concluyente: F1 macro ({f1_macro:.3f}) o recall de tarea ({recall_tarea:.3f}) "
            "se ubican en zona intermedia."
        )

    return {
        "f1_macro": f1_macro,
        "recall_tarea": recall_tarea,
        "veredicto": veredicto,
        "motivo": motivo,
    }


def generar_predicciones_simuladas(
    etiquetas_reales: Sequence[str],
    semilla: int = 42,
    ruido_pct: float = 0.15,
) -> list[str]:
    """Genera predicciones simuladas deterministas con ligera perturbación para pruebas controladas."""
    rng = random.Random(semilla)
    preds: list[str] = []
    for y in etiquetas_reales:
        if rng.random() > ruido_pct and y in CLASES_DETECTOR:
            preds.append(y)
        else:
            candidatos = [c for c in CLASES_DETECTOR if c != y]
            preds.append(rng.choice(candidatos) if candidatos else y)
    return preds


def evaluar_detector_csv(
    ruta_csv: str | Path,
    modelo: str | None = None,
    predicciones: Sequence[str] | None = None,
    simulado: bool = False,
    semilla: int = 42,
) -> dict[str, Any]:
    """Evalúa el detector sobre un archivo CSV etiquetado manualmente."""
    p_csv = Path(ruta_csv)
    if not p_csv.exists():
        raise FileNotFoundError(f"Archivo de etiquetas no encontrado: {p_csv}")

    etiquetas_reales: list[str] = []
    textos: list[str] = []
    filas_csv: list[dict[str, str]] = []

    with open(p_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lbl = row.get("etiqueta_humana", "").strip().lower()
            if not lbl:
                continue
            etiquetas_reales.append(lbl)
            textos.append(row.get("texto", "").strip())
            filas_csv.append(row)

    if not etiquetas_reales:
        raise ValueError(f"No se encontraron etiquetas válidas en {p_csv}")

    if predicciones is not None:
        y_pred = list(predicciones)
    elif simulado or not modelo:
        y_pred = generar_predicciones_simuladas(etiquetas_reales, semilla=semilla)
    else:
        # Cargar modelo HuggingFace / detector si está disponible
        y_pred = _predecir_con_modelo(textos, modelo)

    metricas = calcular_metricas_clasificacion(etiquetas_reales, y_pred)
    recall_tarea = float(metricas["por_clase"]["tarea"]["recall"])
    eval_h4 = evaluar_hipotesis_h4(metricas["f1_macro"], recall_tarea)

    return {
        "ruta_csv": str(p_csv),
        "total_segmentos": len(etiquetas_reales),
        "simulado": simulado or (predicciones is None and not modelo),
        "modelo": modelo or "simulado_determinista",
        "metricas": metricas,
        "evaluacion_h4": eval_h4,
    }


def _predecir_con_modelo(textos: Sequence[str], modelo_id: str) -> list[str]:
    """Infiere etiquetas con modelo HuggingFace o módulo de detector."""
    try:
        from transformers import pipeline  # type: ignore
        clasificador = pipeline("text-classification", model=modelo_id, truncation=True)
        resultados = clasificador(list(textos))
        return [str(r["label"]).lower() for r in resultados]
    except Exception as exc:
        print(f"ADVERTENCIA: No se pudo inferir con {modelo_id} ({exc}). Empleando predicción de respaldo.")
        return [CLASES_DETECTOR[0] for _ in textos]


def imprimir_reporte_detector(resultado: dict[str, Any]) -> None:
    """Imprime en consola el reporte formateado de evaluación H4."""
    metricas = resultado["metricas"]
    eval_h4 = resultado["evaluacion_h4"]

    print("=" * 72)
    print("EVALUACIÓN DE DETECTOR MULTICLASE - HIPÓTESIS H4")
    print("=" * 72)
    if resultado.get("simulado"):
        print(">>> SIMULADO: no es una medición real. No apto para docs/resultados.md <<<")
    print(f"Archivo de evaluación: {resultado.get('ruta_csv', 'N/A')}")
    print(f"Total de segmentos evaluados: {resultado.get('total_segmentos', 0)}")
    print(f"Modelo / Motor: {resultado.get('modelo', 'N/A')}")
    print("-" * 72)
    print(f"{'Clase':<12} | {'Precisión':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Soporte':<8}")
    print("-" * 72)

    for c in CLASES_DETECTOR:
        m = metricas["por_clase"][c]
        print(
            f"{c:<12} | "
            f"{m['precision']*100:>8.2f} % | "
            f"{m['recall']*100:>8.2f} % | "
            f"{m['f1']*100:>8.2f} % | "
            f"{m['support']:>8}"
        )

    print("-" * 72)
    print(f"{'Macro avg':<12} | {metricas['precision_macro']*100:>8.2f} % | {metricas['recall_macro']*100:>8.2f} % | {metricas['f1_macro']*100:>8.2f} % | {metricas['total_muestras']:>8}")
    print(f"{'Accuracy':<12} | {' ':>10} | {' ':>10} | {metricas['accuracy']*100:>8.2f} % | {metricas['total_muestras']:>8}")
    print("=" * 72)
    print("Veredicto de Hipótesis H4:")
    print(f"  F1 macro observado     : {eval_h4['f1_macro']*100:.2f} % (umbral >= {UMBRAL_F1_CONFIRMADA*100:.1f}%)")
    print(f"  Recall 'tarea' observado: {eval_h4['recall_tarea']*100:.2f} % (umbral >= {UMBRAL_RECALL_TAREA_CONFIRMADA*100:.1f}%)")
    print(f"  VEREDICTO              : {eval_h4['veredicto'].value}")
    print(f"  Detalle                : {eval_h4['motivo']}")
    print("=" * 72)


def main() -> None:
    """Punto de entrada de línea de comandos."""
    parser = argparse.ArgumentParser(description="Evaluación de generalización del detector multiclase (H4)")
    parser.add_argument("--modelo", type=str, default=None, help="ID o ruta local del modelo clasificador")
    parser.add_argument("--etiquetas", type=str, default="data/eval/reunion_etiquetada.csv", help="Ruta al CSV con etiquetas humanas")
    parser.add_argument("--simulado", action="store_true", help="Ejecutar en modo simulado para pruebas de integración")

    args = parser.parse_args()

    ruta_csv = Path(args.etiquetas)
    if not ruta_csv.exists() and not args.simulado:
        print(f"ERROR: No se encontró el archivo de etiquetas en '{args.etiquetas}'.")
        print("Use --simulado para pruebas o ejecute la tarea de etiquetado HU06 primero.")
        sys.exit(1)

    if not ruta_csv.exists() and args.simulado:
        # Generar un dataset simulado en memoria para permitir prueba de humo CLI
        filas_mock = [
            {"id": str(i), "inicio_s": "0.0", "fin_s": "5.0", "orador": "A", "texto": f"Txt {i}", "etiqueta_humana": c}
            for i, c in enumerate(CLASES_DETECTOR * 5)
        ]
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tf:
            writer = csv.DictWriter(tf, fieldnames=list(filas_mock[0].keys()))
            writer.writeheader()
            writer.writerows(filas_mock)
            temp_path = tf.name

        try:
            res = evaluar_detector_csv(temp_path, modelo=args.modelo, simulado=True)
        finally:
            Path(temp_path).unlink(missing_ok=True)
    else:
        res = evaluar_detector_csv(ruta_csv, modelo=args.modelo, simulado=args.simulado)

    imprimir_reporte_detector(res)


if __name__ == "__main__":
    main()
