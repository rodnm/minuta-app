"""Pruebas unitarias para el arnés de evaluación de eficiencia (evaluacion/eficiencia.py).

Verifica el cálculo de ahorro de tokens y tiempo, y las reglas de decisión de
las hipótesis pre-registradas H5a (reuniones) y H5b (ponencias).
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from evaluacion.eficiencia import (
    VeredictoH5a,
    VeredictoH5b,
    calcular_ahorro_relativo,
    evaluar_hipotesis_h5a,
    evaluar_hipotesis_h5b,
    evaluar_eficiencia_archivo,
)


def test_calcular_ahorro_relativo():
    """Verifica el cálculo de porcentaje de ahorro entre base y optimizado."""
    # De 1000 a 400 es un 60% de ahorro
    ahorro = calcular_ahorro_relativo(base=1000.0, optimizado=400.0)
    assert ahorro == pytest.approx(60.0)

    # Si base es 0, no debe dividir por cero
    assert calcular_ahorro_relativo(base=0.0, optimizado=0.0) == 0.0


def test_evaluar_hipotesis_h5a_confirmada():
    """H5a: confirmada si ahorro tokens >= 60%, ahorro tiempo >= 40% y caída recall <= 5 pts."""
    res = evaluar_hipotesis_h5a(
        ahorro_tokens_pct=62.0,
        ahorro_tiempo_pct=45.0,
        caida_recall_todos_pts=3.0,
    )
    assert res["veredicto"] == VeredictoH5a.CONFIRMADA
    assert "Confirmada" in res["motivo"]


def test_evaluar_hipotesis_h5a_falsada_por_ahorro():
    """H5a: falsada si ahorro tokens < 40%."""
    res = evaluar_hipotesis_h5a(
        ahorro_tokens_pct=35.0,
        ahorro_tiempo_pct=45.0,
        caida_recall_todos_pts=2.0,
    )
    assert res["veredicto"] == VeredictoH5a.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h5a_falsada_por_caida_recall():
    """H5a: falsada si caída de recall > 10 pts."""
    res = evaluar_hipotesis_h5a(
        ahorro_tokens_pct=65.0,
        ahorro_tiempo_pct=45.0,
        caida_recall_todos_pts=12.0,
    )
    assert res["veredicto"] == VeredictoH5a.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h5b_confirmada():
    """H5b: confirmada si ahorro tokens >= 25% y caída cobertura nivel 2 <= 10%."""
    res = evaluar_hipotesis_h5b(
        ahorro_tokens_pct=28.0,
        caida_cobertura_pct=5.0,
    )
    assert res["veredicto"] == VeredictoH5b.CONFIRMADA
    assert "Confirmada" in res["motivo"]


def test_evaluar_hipotesis_h5b_falsada_por_ahorro():
    """H5b: falsada si ahorro tokens < 10%."""
    res = evaluar_hipotesis_h5b(
        ahorro_tokens_pct=8.0,
        caida_cobertura_pct=5.0,
    )
    assert res["veredicto"] == VeredictoH5b.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_eficiencia_archivo_simulado(tmp_path: Path):
    """Verifica la ejecución del evaluador de eficiencia en modo simulado sobre un archivo de reunión."""
    entrada = tmp_path / "reunion_test.json"
    data = {
        "audio_id": "test_01",
        "duracion_s": 600.0,
        "segmentos": [
            {"id": i, "inicio_s": i * 10.0, "fin_s": (i + 1) * 10.0, "texto": f"Segmento de prueba {i}"}
            for i in range(20)
        ],
    }
    with open(entrada, "w", encoding="utf-8") as f:
        json.dump(data, f)

    res = evaluar_eficiencia_archivo(
        ruta_entrada=entrada,
        tipo="reunion",
        simulado=True,
    )

    assert res["simulado"] is True
    assert "ahorro_tokens_pct" in res
    assert "ahorro_tiempo_pct" in res
    assert res["evaluacion"]["veredicto"] in [VeredictoH5a.CONFIRMADA, VeredictoH5a.FALSADA, VeredictoH5a.NO_CONCLUYENTE]
