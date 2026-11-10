"""Pruebas unitarias para el arnés de evaluación de detector (evaluacion/detector.py).

Verifica el cálculo de métricas de clasificación multiclase (idea, tarea, acuerdo,
pregunta, relleno) y las reglas de decisión de la hipótesis pre-registrada H4.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest

from evaluacion.detector import (
    CLASES_DETECTOR,
    VeredictoH4,
    calcular_metricas_clasificacion,
    evaluar_hipotesis_h4,
    evaluar_detector_csv,
    generar_predicciones_simuladas,
)


def test_clases_detector_definidas():
    """Verifica que las 5 clases requeridas estén contempladas."""
    esperadas = {"idea", "tarea", "acuerdo", "pregunta", "relleno"}
    assert set(CLASES_DETECTOR) == esperadas


def test_calcular_metricas_clasificacion_perfecta():
    """Verifica métricas con predicciones idénticas a las etiquetas reales."""
    y_true = ["idea", "tarea", "acuerdo", "pregunta", "relleno"] * 10
    y_pred = list(y_true)

    metricas = calcular_metricas_clasificacion(y_true, y_pred)

    assert metricas["f1_macro"] == pytest.approx(1.0)
    assert metricas["accuracy"] == pytest.approx(1.0)
    assert metricas["por_clase"]["tarea"]["recall"] == pytest.approx(1.0)
    assert metricas["por_clase"]["tarea"]["f1"] == pytest.approx(1.0)
    assert metricas["total_muestras"] == 50


def test_evaluar_hipotesis_h4_confirmada():
    """H4 se confirma si F1 macro >= 0.70 y recall de tarea >= 0.80."""
    res = evaluar_hipotesis_h4(f1_macro=0.75, recall_tarea=0.85)
    assert res["veredicto"] == VeredictoH4.CONFIRMADA
    assert "Confirmada" in res["motivo"]


def test_evaluar_hipotesis_h4_falsada_por_f1():
    """H4 se falsa si F1 macro < 0.55."""
    res = evaluar_hipotesis_h4(f1_macro=0.52, recall_tarea=0.85)
    assert res["veredicto"] == VeredictoH4.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h4_falsada_por_recall_tarea():
    """H4 se falsa si recall de tarea < 0.65."""
    res = evaluar_hipotesis_h4(f1_macro=0.75, recall_tarea=0.60)
    assert res["veredicto"] == VeredictoH4.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h4_no_concluyente_zona_intermedia():
    """H4 es no concluyente/intermedia cuando está entre 0.55 y 0.70 o recall 0.65 y 0.80 sin falsar."""
    res = evaluar_hipotesis_h4(f1_macro=0.65, recall_tarea=0.75)
    assert res["veredicto"] == VeredictoH4.NO_CONCLUYENTE
    assert "No concluyente" in res["motivo"]


def test_generar_predicciones_simuladas():
    """Verifica que el generador simulado sea determinista y devuelva etiquetas válidas."""
    etiquetas_reales = ["idea", "tarea", "relleno", "acuerdo", "pregunta"]
    preds_1 = generar_predicciones_simuladas(etiquetas_reales, semilla=42)
    preds_2 = generar_predicciones_simuladas(etiquetas_reales, semilla=42)

    assert preds_1 == preds_2
    assert len(preds_1) == len(etiquetas_reales)
    for p in preds_1:
        assert p in CLASES_DETECTOR


def test_evaluar_detector_csv(tmp_path: Path):
    """Verifica la evaluación desde un archivo CSV con las columnas de plantilla."""
    csv_file = tmp_path / "test_etiquetas.csv"
    filas = [
        {"id": "1", "inicio_s": "0.0", "fin_s": "5.0", "orador": "A", "texto": "T1", "etiqueta_humana": "idea"},
        {"id": "2", "inicio_s": "5.0", "fin_s": "10.0", "orador": "B", "texto": "T2", "etiqueta_humana": "tarea"},
        {"id": "3", "inicio_s": "10.0", "fin_s": "15.0", "orador": "A", "texto": "T3", "etiqueta_humana": "acuerdo"},
        {"id": "4", "inicio_s": "15.0", "fin_s": "20.0", "orador": "B", "texto": "T4", "etiqueta_humana": "pregunta"},
        {"id": "5", "inicio_s": "20.0", "fin_s": "25.0", "orador": "A", "texto": "T5", "etiqueta_humana": "relleno"},
    ]
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)

    # Evaluación con predicciones mock idénticas
    res = evaluar_detector_csv(
        ruta_csv=csv_file,
        predicciones=["idea", "tarea", "acuerdo", "pregunta", "relleno"],
    )

    assert res["metricas"]["f1_macro"] == pytest.approx(1.0)
    assert res["evaluacion_h4"]["veredicto"] == VeredictoH4.CONFIRMADA
