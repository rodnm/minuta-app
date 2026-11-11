"""Pruebas unitarias para la evaluación H1b con LLM (evaluacion/terminos_llm.py).

Verifica la lógica de evaluación con salida estructurada de LLM, normalización
de términos técnicos en inglés, umbrales pre-registrados de H1/H1b y ejecución simulada.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluacion.terminos_llm import (
    construir_prompt,
    evaluar_hipotesis_h1b,
    normalizar_termino,
    coincide_termino,
    ejecutar_evaluacion_llm,
    VeredictoH1b,
    TerminoDetectado,
    FraseConTerminos,
    EvaluacionH1b,
)


def test_normalizar_termino() -> None:
    assert normalizar_termino("JSON") == "json"
    assert normalizar_termino("Peer-Review") == "peer review"
    assert normalizar_termino("  Trade-Off  ") == "trade off"
    assert normalizar_termino("arXiv") == "arxiv"


def test_coincide_termino() -> None:
    # Coincidencia exacta insensible a mayúsculas
    assert coincide_termino("JSON", ["json"])
    assert coincide_termino("peer-review", ["peer review"])
    assert coincide_termino("trade-off", ["trade-off"])
    # Coincidencia contenida
    assert coincide_termino("working paper", ["working papers"])
    assert coincide_termino("randomized controlled trial", ["randomized controlled trials"])
    # No coincidencia
    assert not coincide_termino("JSON", ["xml", "csv"])


def test_evaluar_hipotesis_h1b_umbrales() -> None:
    # Línea base = 0.86 (43/50)
    # Falsada: recall < 0.70 o mejora < 10 pts
    res_falsada_1 = evaluar_hipotesis_h1b(recall=0.68, linea_base=0.86)
    assert res_falsada_1["veredicto"] == VeredictoH1b.FALSADA

    res_falsada_2 = evaluar_hipotesis_h1b(recall=0.90, linea_base=0.86) # mejora = +4 pts (< 10)
    assert res_falsada_2["veredicto"] == VeredictoH1b.FALSADA

    # Confirmada: recall >= 0.85 y mejora >= 15 pts (>= 1.01, impracticable con base 0.86, pero lógica formal)
    res_conf = evaluar_hipotesis_h1b(recall=0.88, linea_base=0.70) # mejora = +18 pts
    assert res_conf["veredicto"] == VeredictoH1b.CONFIRMADA

    # No concluyente: zona intermedia (mejora entre 10 y 15 pts, recall >= 0.85)
    # Ejemplo real H1b: recall = 0.98 (49/50), mejora = +12.00 pts
    res_intermedia = evaluar_hipotesis_h1b(recall=0.98, linea_base=0.86)
    assert res_intermedia["veredicto"] == VeredictoH1b.NO_CONCLUYENTE
    assert pytest.approx(res_intermedia["mejora_pts"], 0.01) == 12.00


def test_construir_prompt_sin_y_con_pistas() -> None:
    transcripciones = [{"id": 1, "transcripcion": "Usamos un archivo Jason para el dataset."}]
    
    prompt_sin = construir_prompt(transcripciones, con_pistas=False)
    assert "RCIP" not in prompt_sin
    assert "on-working paper" not in prompt_sin
    assert "[01] Usamos un archivo Jason para el dataset." in prompt_sin

    prompt_con = construir_prompt(transcripciones, con_pistas=True)
    assert "RCIP" in prompt_con or "pista" in prompt_con.lower() or "deformaciones" in prompt_con
    assert "[01] Usamos un archivo Jason para el dataset." in prompt_con


def test_ejecutar_evaluacion_llm_simulado() -> None:
    resultado = ejecutar_evaluacion_llm(
        guion_path=ROOT_DIR / "evaluacion" / "guion_frases.json",
        modo_simulado=True,
        con_pistas=False,
    )
    assert resultado["total_esperados"] == 50
    assert resultado["total_aciertos"] >= 40
    assert 0.0 <= resultado["recall"] <= 1.0
    assert "veredicto" in resultado
    assert "detalles" in resultado
    assert len(resultado["detalles"]) == 25
