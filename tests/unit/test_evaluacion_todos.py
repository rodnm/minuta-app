"""Pruebas unitarias para el arnés de evaluación de to-dos (evaluacion/todos.py).

Verifica la validación de citas literales, emparejamiento semántico/léxico con
referencias y las reglas de decisión de la hipótesis pre-registrada H8.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import pytest

from evaluacion.todos import (
    VeredictoH8,
    evaluar_citas_literales,
    emparejar_todos,
    evaluar_hipotesis_h8,
    evaluar_archivo_todos,
    main as todos_main,
)

FIXTURE_PRED = Path("data/fixtures/resultado_reunion.json")
FIXTURE_TRANS = Path("data/fixtures/transcripcion_reunion.json")


def test_evaluar_citas_literales_todas_validas():
    """Verifica que si todas las citas son literales, el porcentaje sea 100%."""
    segmentos = [
        {"id": 1, "inicio_s": 0.0, "fin_s": 5.0, "texto": "Tenemos que enviar el reporte antes del viernes."},
        {"id": 2, "inicio_s": 5.0, "fin_s": 10.0, "texto": "Carlos coordinará la reunión con el equipo técnico."},
    ]
    tareas = [
        {"descripcion": "Enviar reporte", "evidencia": {"segmento_ids": [1], "inicio_s": 0.0, "cita": "enviar el reporte antes del viernes"}},
        {"descripcion": "Coordinar reunión", "evidencia": {"segmento_ids": [2], "inicio_s": 5.0, "cita": "Carlos coordinará la reunión"}},
    ]

    res = evaluar_citas_literales(tareas, segmentos)
    assert res["total_tareas"] == 2
    assert res["citas_validas"] == 2
    assert res["pct_citas_literales"] == pytest.approx(100.0)
    assert res["todas_literales"] is True


def test_evaluar_citas_literales_fallo():
    """Verifica que si una cita no existe en la transcripción, el porcentaje caiga."""
    segmentos = [
        {"id": 1, "inicio_s": 0.0, "fin_s": 5.0, "texto": "Tenemos que enviar el reporte."},
    ]
    tareas = [
        {"descripcion": "Tarea inventada", "evidencia": {"segmento_ids": [1], "inicio_s": 0.0, "cita": "comprar servidores nuevos en la nube"}},
    ]

    res = evaluar_citas_literales(tareas, segmentos)
    assert res["citas_validas"] == 0
    assert res["pct_citas_literales"] == pytest.approx(0.0)
    assert res["todas_literales"] is False


def test_emparejar_todos_perfecto():
    """Verifica precisión y recall cuando las tareas predichas coinciden con la referencia."""
    predichas = [
        {"descripcion": "Enviar el borrador del paper al journal antes del viernes"},
        {"descripcion": "Configurar script de verificación de credenciales"},
    ]
    referencias = [
        {"descripcion": "Enviar borrador del paper al journal"},
        {"descripcion": "Configurar el script verificar.py"},
    ]

    res = emparejar_todos(predichas, referencias, umbral_similitud=0.4)
    assert res["tp"] == 2
    assert res["fp"] == 0
    assert res["fn"] == 0
    assert res["precision"] == pytest.approx(1.0)
    assert res["recall"] == pytest.approx(1.0)


def test_evaluar_hipotesis_h8_confirmada():
    """H8 se confirma si precisión >= 0.80, recall >= 0.70 y 100% citas literales."""
    res = evaluar_hipotesis_h8(precision=0.85, recall=0.75, pct_citas_literales=100.0)
    assert res["veredicto"] == VeredictoH8.CONFIRMADA
    assert "Confirmada" in res["motivo"]


def test_evaluar_hipotesis_h8_falsada_por_citas():
    """H8 se falsa si alguna cita no es literal (< 100%)."""
    res = evaluar_hipotesis_h8(precision=0.90, recall=0.85, pct_citas_literales=95.0)
    assert res["veredicto"] == VeredictoH8.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h8_falsada_por_precision():
    """H8 se falsa si precisión < 0.65."""
    res = evaluar_hipotesis_h8(precision=0.60, recall=0.85, pct_citas_literales=100.0)
    assert res["veredicto"] == VeredictoH8.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_archivo_todos_con_fixture_reunion():
    """Verifica la evaluación usando el fixture real de reunión."""
    fixture_pred = Path("data/fixtures/resultado_reunion.json")
    fixture_trans = Path("data/fixtures/transcripcion_reunion.json")

    assert fixture_pred.exists()
    assert fixture_trans.exists()

    res = evaluar_archivo_todos(
        ruta_pred=fixture_pred,
        ruta_transcripcion=fixture_trans,
        simulado=True,
    )

    assert res["citas"]["pct_citas_literales"] == pytest.approx(100.0)
    assert res["citas"]["total_tareas"] == 5
    assert res["simulado"] is True


def test_cli_ref_inexistente_sale_con_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """C1 (L51): una --ref que no existe es un error, nunca una autocomparación CONFIRMADA."""
    ref_inexistente = tmp_path / "no_existe.csv"

    with pytest.raises(FileNotFoundError, match="no_existe.csv"):
        evaluar_archivo_todos(
            ruta_pred=FIXTURE_PRED,
            ruta_ref=ref_inexistente,
            ruta_transcripcion=FIXTURE_TRANS,
        )

    argv = [
        "todos.py",
        "--pred", str(FIXTURE_PRED),
        "--transcripcion", str(FIXTURE_TRANS),
        "--ref", str(ref_inexistente),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as salida:
        todos_main()

    assert salida.value.code == 1
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "no_existe.csv" in out
    assert "CONFIRMADA" not in out


def test_cli_ref_valida_mantiene_veredicto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Comportamiento previo: con una --ref válida se compara contra ella y no se marca simulado."""
    datos = json.loads(FIXTURE_PRED.read_text(encoding="utf-8"))
    ref = tmp_path / "todos_manual.csv"
    with open(ref, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["descripcion", "responsable", "fecha_limite"])
        for t in datos["tareas"]:
            escritor.writerow([t["descripcion"], "", ""])

    res = evaluar_archivo_todos(ruta_pred=FIXTURE_PRED, ruta_ref=ref, ruta_transcripcion=FIXTURE_TRANS)
    assert res["simulado"] is False
    assert res["ruta_ref"] == str(ref)
    assert res["emparejamiento"]["tp"] == 5
    assert res["evaluacion_h8"]["veredicto"] == VeredictoH8.CONFIRMADA

    argv = [
        "todos.py",
        "--pred", str(FIXTURE_PRED),
        "--transcripcion", str(FIXTURE_TRANS),
        "--ref", str(ref),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    todos_main()
    out = capsys.readouterr().out
    assert "VEREDICTO : CONFIRMADA" in out
    assert "SIMULADO" not in out
