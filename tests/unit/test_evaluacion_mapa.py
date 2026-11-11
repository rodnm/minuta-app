"""Pruebas unitarias para el arnés de evaluación de mapas mentales (evaluacion/mapa.py).

Verifica la validación estructural del árbol MapaMental (profundidad, ramas principales,
evidencias válidas) y las reglas de decisión de la hipótesis pre-registrada H9.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from minuta.esquemas import Evidencia, MapaMental, NodoMapa
from evaluacion.mapa import (
    VeredictoH9,
    analizar_estructura_mapa,
    evaluar_hipotesis_h9,
    evaluar_mapa_archivo,
    main as mapa_main,
)


def test_analizar_estructura_mapa_arbol_simple():
    """Verifica el cálculo de profundidad, ramas principales y porcentaje de citas en un árbol controlado."""
    arbol = MapaMental(
        titulo="Mapa de Prueba",
        raiz=NodoMapa(
            id="root",
            titulo="Raíz",
            evidencia=None,
            hijos=[
                NodoMapa(
                    id="r1",
                    titulo="Rama 1",
                    evidencia=Evidencia(segmento_ids=[1], inicio_s=0.0, cita="Cita uno"),
                    hijos=[
                        NodoMapa(
                            id="r1_sub",
                            titulo="Subtema 1",
                            evidencia=Evidencia(segmento_ids=[2], inicio_s=10.0, cita="Cita dos"),
                        )
                    ],
                ),
                NodoMapa(
                    id="r2",
                    titulo="Rama 2",
                    evidencia=Evidencia(segmento_ids=[3], inicio_s=20.0, cita="Cita tres"),
                ),
            ],
        ),
    )

    stats = analizar_estructura_mapa(arbol)

    assert stats["total_nodos_sin_raiz"] == 3
    assert stats["nodos_con_cita"] == 3
    assert stats["pct_nodos_con_cita"] == pytest.approx(100.0)
    assert stats["ramas_principales"] == 2
    assert stats["profundidad_maxima"] == 3


def test_evaluar_hipotesis_h9_confirmada():
    """H9: confirmada si >= 90% citas literales, profundidad entre 2 y 4, ramas entre 4 y 8."""
    res = evaluar_hipotesis_h9(
        pct_citas_literales=95.0,
        profundidad=3,
        ramas_principales=5,
    )
    assert res["veredicto"] == VeredictoH9.CONFIRMADA
    assert "Confirmada" in res["motivo"]


def test_evaluar_hipotesis_h9_falsada_por_citas():
    """H9: falsada si porcentaje de citas literales < 75%."""
    res = evaluar_hipotesis_h9(
        pct_citas_literales=70.0,
        profundidad=3,
        ramas_principales=5,
    )
    assert res["veredicto"] == VeredictoH9.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h9_no_concluyente():
    """H9: no concluyente si citas entre 75% y 90% o profundidad/ramas fuera de rango ideal."""
    res = evaluar_hipotesis_h9(
        pct_citas_literales=82.0,
        profundidad=3,
        ramas_principales=5,
    )
    assert res["veredicto"] == VeredictoH9.NO_CONCLUYENTE
    assert "No concluyente" in res["motivo"]


def test_evaluar_mapa_archivo_fixture_ponencia():
    """Verifica la evaluación del mapa mental en el fixture real de ponencia."""
    fixture_ponencia = Path("data/fixtures/resultado_ponencia.json")
    fixture_trans = Path("data/fixtures/transcripcion_ponencia.json")

    assert fixture_ponencia.exists()
    assert fixture_trans.exists()

    res = evaluar_mapa_archivo(
        ruta_pred=fixture_ponencia,
        ruta_transcripcion=fixture_trans,
    )

    # En el fixture de ponencia, todos los nodos no raíz tienen cita válida
    assert res["stats"]["pct_nodos_con_cita"] == pytest.approx(100.0)
    assert res["stats"]["profundidad_maxima"] == 3
    assert res["stats"]["citas_literales_validadas"] == res["stats"]["nodos_con_cita"]
    # Comportamiento previo: el fixture tiene 3 ramas (< 4), así que el veredicto no cambia
    assert res["stats"]["pct_citas_literales"] == pytest.approx(100.0)
    assert res["evaluacion_h9"]["veredicto"] == VeredictoH9.NO_CONCLUYENTE


TRANSCRIPCION_CORTA = {
    "audio_id": "prueba",
    "segmentos": [
        {"id": 1, "inicio_s": 0.0, "fin_s": 8.0, "texto": "Hoy revisamos el proceso de peer review con revisores ciegos."},
        {"id": 2, "inicio_s": 8.0, "fin_s": 16.0, "texto": "Luego hablamos del financiamiento con fondos concursables."},
    ],
}


def _nodo(indice: int, hijos: list[dict] | None = None) -> dict:
    return {
        "id": f"n{indice}",
        "titulo": f"Tema {indice}",
        "evidencia": {
            "segmento_ids": [1],
            "inicio_s": 0.0,
            "cita": f"esta frase inventada numero {indice} jamas fue pronunciada",
        },
        "hijos": hijos or [],
    }


def _escribir_mapa_inventado(tmp_path: Path) -> Path:
    """Mapa con 5 ramas y 3 niveles (estructura ideal) pero con todas las citas inventadas."""
    mapa = {
        "mapa": {
            "titulo": "Mapa con citas inventadas",
            "raiz": {
                "id": "root",
                "titulo": "Raíz",
                "evidencia": None,
                "hijos": [_nodo(1, [_nodo(11)]), _nodo(2, [_nodo(21)]), _nodo(3), _nodo(4), _nodo(5)],
            },
        }
    }
    ruta = tmp_path / "resultado_inventado.json"
    ruta.write_text(json.dumps(mapa, ensure_ascii=False), encoding="utf-8")
    return ruta


def _escribir_transcripcion(tmp_path: Path, datos: dict) -> Path:
    ruta = tmp_path / "transcripcion_corta.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_cli_citas_inventadas_no_confirman_h9(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """C2 (L51): H9 decide con el % de citas literales cotejadas, no con el % de nodos con cita."""
    pred = _escribir_mapa_inventado(tmp_path)
    trans = _escribir_transcripcion(tmp_path, TRANSCRIPCION_CORTA)

    res = evaluar_mapa_archivo(ruta_pred=pred, ruta_transcripcion=trans)
    assert res["stats"]["pct_nodos_con_cita"] == pytest.approx(100.0)
    assert res["stats"]["pct_citas_literales"] == pytest.approx(0.0)
    assert res["evaluacion_h9"]["veredicto"] == VeredictoH9.FALSADA

    monkeypatch.setattr(sys, "argv", ["mapa.py", "--pred", str(pred), "--transcripcion", str(trans)])
    mapa_main()
    out = capsys.readouterr().out
    assert "VEREDICTO : FALSADA" in out
    assert "CONFIRMADA" not in out


def test_transcripcion_obligatoria_para_h9(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """C2 (L51): sin transcripción no hay forma de cotejar las citas, así que la llamada falla con claridad."""
    pred = _escribir_mapa_inventado(tmp_path)

    with pytest.raises(ValueError, match="transcripción"):
        evaluar_mapa_archivo(ruta_pred=pred)

    with pytest.raises(FileNotFoundError, match="no_existe.json"):
        evaluar_mapa_archivo(ruta_pred=pred, ruta_transcripcion=tmp_path / "no_existe.json")

    sin_segmentos = _escribir_transcripcion(tmp_path, {"audio_id": "vacia", "segmentos": []})
    with pytest.raises(ValueError, match="segmentos"):
        evaluar_mapa_archivo(ruta_pred=pred, ruta_transcripcion=sin_segmentos)

    # Sin segmentos, ninguna cita cuenta como literal
    stats = analizar_estructura_mapa(json.loads(pred.read_text(encoding="utf-8")))
    assert stats["nodos_con_cita"] == 7
    assert stats["citas_literales_validadas"] == 0

    monkeypatch.setattr(sys, "argv", ["mapa.py", "--pred", str(pred)])
    with pytest.raises(SystemExit) as salida:
        mapa_main()
    assert salida.value.code != 0
    capturado = capsys.readouterr()
    assert "--transcripcion" in capturado.err
    assert "CONFIRMADA" not in capturado.out
