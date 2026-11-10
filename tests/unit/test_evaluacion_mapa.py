"""Pruebas unitarias para el arnés de evaluación de mapas mentales (evaluacion/mapa.py).

Verifica la validación estructural del árbol MapaMental (profundidad, ramas principales,
evidencias válidas) y las reglas de decisión de la hipótesis pre-registrada H9.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from minuta.esquemas import Evidencia, MapaMental, NodoMapa
from evaluacion.mapa import (
    VeredictoH9,
    analizar_estructura_mapa,
    evaluar_hipotesis_h9,
    evaluar_mapa_archivo,
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
    """H9: confirmada si >= 90% citas, profundidad entre 2 y 4, ramas entre 4 y 8."""
    res = evaluar_hipotesis_h9(
        pct_nodos_con_cita=95.0,
        profundidad=3,
        ramas_principales=5,
    )
    assert res["veredicto"] == VeredictoH9.CONFIRMADA
    assert "Confirmada" in res["motivo"]


def test_evaluar_hipotesis_h9_falsada_por_citas():
    """H9: falsada si porcentaje de citas < 75%."""
    res = evaluar_hipotesis_h9(
        pct_nodos_con_cita=70.0,
        profundidad=3,
        ramas_principales=5,
    )
    assert res["veredicto"] == VeredictoH9.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h9_no_concluyente():
    """H9: no concluyente si citas entre 75% y 90% o profundidad/ramas fuera de rango ideal."""
    res = evaluar_hipotesis_h9(
        pct_nodos_con_cita=82.0,
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
