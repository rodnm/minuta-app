"""Pruebas unitarias para el arnés de evaluación de eficiencia (evaluacion/eficiencia.py).

Verifica el cálculo de ahorro de tokens y tiempo, y las reglas de decisión de
las hipótesis pre-registradas H5a (reuniones) y H5b (ponencias).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from evaluacion.eficiencia import (
    VeredictoH5a,
    VeredictoH5b,
    calcular_ahorro_relativo,
    evaluar_hipotesis_h5a,
    evaluar_hipotesis_h5b,
    evaluar_eficiencia_archivo,
    main as eficiencia_main,
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
    # Comportamiento previo: el modo --simulado conserva sus parámetros de diseño
    assert res["ahorro_tokens_pct"] == pytest.approx(62.5)
    assert res["ahorro_tiempo_pct"] == pytest.approx(44.0)


@pytest.mark.parametrize(
    ("tipo", "contenido"),
    [
        ("reunion", {"tareas": [{"descripcion": "Enviar el informe"}], "acuerdos": []}),
        ("ponencia", {"ideas_clave": ["Idea uno"], "preguntas": []}),
    ],
)
def test_entrada_sin_segmentos_es_simulada_y_no_confirma(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    tipo: str,
    contenido: dict,
):
    """C3a (L51): sin segmentos no hay medición; se rotula SIMULADO y nunca da CONFIRMADA."""
    entrada = tmp_path / f"resultado_{tipo}.json"
    entrada.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")

    res = evaluar_eficiencia_archivo(ruta_entrada=entrada, tipo=tipo)
    assert res["simulado"] is True
    assert res["evaluacion"]["veredicto"].value != "CONFIRMADA"

    monkeypatch.setattr(sys, "argv", ["eficiencia.py", "--entrada", str(entrada), "--tipo", tipo])
    eficiencia_main()
    out = capsys.readouterr().out
    assert ">>> SIMULADO" in out
    assert "CONFIRMADA" not in out


def test_rama_con_etiqueta_de_referencia_no_es_valida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """C3b (L51): filtrar por la etiqueta de referencia no mide un detector; sin detector entrenado es un error."""
    segmentos = [
        {"id": i, "inicio_s": i * 10.0, "fin_s": (i + 1) * 10.0,
         "texto": f"bueno este eh como les decía el tema numero {i} de hoy",
         "etiqueta": "relleno" if i % 4 else "tarea"}
        for i in range(20)
    ]
    entrada = tmp_path / "transcripcion_reunion.json"
    entrada.write_text(json.dumps({"audio_id": "x", "segmentos": segmentos}, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="detector"):
        evaluar_eficiencia_archivo(ruta_entrada=entrada, tipo="reunion")

    monkeypatch.setattr(sys, "argv", ["eficiencia.py", "--entrada", str(entrada), "--tipo", "reunion"])
    with pytest.raises(SystemExit) as salida:
        eficiencia_main()
    assert salida.value.code == 1
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "VEREDICTO" not in out
