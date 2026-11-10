"""Pruebas unitarias para el detector de segmentos de Minuta (T20, S4, H5a, H5b).

Metodología test-first.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from minuta.esquemas import (
    Evidencia,
    MapaMental,
    NodoMapa,
    ResultadoPonencia,
    ResultadoReunion,
    Segmento,
    Transcripcion,
)
from minuta.detector import DetectorSegmentos
from minuta.estructurar import estructurar_transcripcion
from minuta.proveedores import ProveedorMock


# ---------------------------------------------------------------------------
# 1. Pruebas de Inicialización y Fallback Defensivo
# ---------------------------------------------------------------------------

def test_detector_no_disponible_con_ruta_inexistente():
    detector = DetectorSegmentos(modelo_id="ruta/inexistente/modelo")
    assert detector.disponible is False

    segs = [Segmento(id=1, inicio_s=0.0, fin_s=3.0, texto="Hola a todos.")]
    with pytest.raises(RuntimeError, match="no está disponible"):
        detector.clasificar(segs)

    # filtrar_relleno no debe fallar cuando no está disponible, retorna todos los segmentos
    retenidos, descartados = detector.filtrar_relleno(segs)
    assert len(retenidos) == 1
    assert descartados == 0


def test_detector_procesar_transcripcion_fallback_solo_llm():
    detector = DetectorSegmentos(modelo_id="ruta/inexistente/modelo")
    tx = Transcripcion(
        audio_id="audio_test",
        duracion_s=10.0,
        modelo="small",
        segmentos=[
            Segmento(id=1, inicio_s=0.0, fin_s=5.0, texto="Buenos días."),
            Segmento(id=2, inicio_s=5.0, fin_s=10.0, texto="Hoy veremos el plan."),
        ],
    )

    proc = detector.procesar_transcripcion(tx)
    assert proc["modo_efectivo"] == "solo_llm"
    assert proc["relleno_descartado"] == 0
    assert len(proc["segmentos_procesados"]) == 2
    assert proc["candidatos_todo"] == []


# ---------------------------------------------------------------------------
# 2. Pruebas con Clasificador Inyectado / Mock
# ---------------------------------------------------------------------------

def test_detector_clasificar_con_mock():
    # Mock que clasifica según palabras clave
    def mock_clasificador(textos: list[str]) -> list[str]:
        etiquetas = []
        for t in textos:
            t_low = t.lower()
            if "buenos días" in t_low or "gracias" in t_low:
                etiquetas.append("relleno")
            elif "debemos" in t_low or "tarea" in t_low:
                etiquetas.append("tarea")
            elif "acordamos" in t_low:
                etiquetas.append("acuerdo")
            elif "¿" in t_low or "?" in t_low:
                etiquetas.append("pregunta")
            else:
                etiquetas.append("idea")
        return etiquetas

    detector = DetectorSegmentos(clasificador=mock_clasificador)
    assert detector.disponible is True

    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=4.0, texto="Buenos días con todos."),
        Segmento(id=2, inicio_s=4.0, fin_s=8.0, texto="La arquitectura mmBERT es eficiente."),
        Segmento(id=3, inicio_s=8.0, fin_s=12.0, texto="Debemos someter el paper hoy."),
        Segmento(id=4, inicio_s=12.0, fin_s=16.0, texto="Acordamos fijar la semilla en 42."),
        Segmento(id=5, inicio_s=16.0, fin_s=20.0, texto="¿Cuál es el deadline final?"),
        Segmento(id=6, inicio_s=20.0, fin_s=24.0, texto="Muchas gracias por su atención."),
    ]

    etiquetas = detector.clasificar(segs)
    assert etiquetas == ["relleno", "idea", "tarea", "acuerdo", "pregunta", "relleno"]

    # Prueba de filtrado de relleno
    retenidos, desc = detector.filtrar_relleno(segs, etiquetas=etiquetas)
    assert desc == 2
    assert len(retenidos) == 4
    ids_retenidos = [s.id for s in retenidos]
    assert ids_retenidos == [2, 3, 4, 5]

    # Prueba de extracción de candidatos to-do (tarea y acuerdo)
    candidatos = detector.extraer_candidatos_todo(segs, etiquetas=etiquetas)
    assert len(candidatos) == 2
    assert candidatos[0].id == 3
    assert candidatos[1].id == 4


def test_detector_procesar_transcripcion_modo_detector():
    def mock_clasificador(textos: list[str]) -> list[str]:
        return ["relleno", "idea", "tarea", "relleno"]

    detector = DetectorSegmentos(clasificador=mock_clasificador)
    tx = Transcripcion(
        audio_id="audio_test_2",
        duracion_s=20.0,
        modelo="small",
        segmentos=[
            Segmento(id=1, inicio_s=0.0, fin_s=5.0, texto="Saludo protocolar."),
            Segmento(id=2, inicio_s=5.0, fin_s=10.0, texto="Propuesta de publicación."),
            Segmento(id=3, inicio_s=10.0, fin_s=15.0, texto="Enviar draft al editor."),
            Segmento(id=4, inicio_s=15.0, fin_s=20.0, texto="Despedida protocolar."),
        ],
    )

    proc = detector.procesar_transcripcion(tx)
    assert proc["modo_efectivo"] == "detector"
    assert proc["relleno_descartado"] == 2
    assert proc["ahorro_segmentos_pct"] == 50.0
    assert len(proc["segmentos_procesados"]) == 2
    assert len(proc["candidatos_todo"]) == 1
    assert proc["candidatos_todo"][0].id == 3


# ---------------------------------------------------------------------------
# 3. Pruebas de Integración con Estructuración Map-Reduce
# ---------------------------------------------------------------------------

def test_estructurar_con_detector_activo_filtra_relleno():
    # Transcripción con 4 segmentos, 2 de los cuales son relleno
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=5.0, texto="Hola buenos días a todos."),
        Segmento(id=2, inicio_s=5.0, fin_s=10.0, texto="Estrategia principal de publicación."),
        Segmento(id=3, inicio_s=10.0, fin_s=15.0, texto="Gestión del proceso de peer review."),
        Segmento(id=4, inicio_s=15.0, fin_s=20.0, texto="Muchas gracias por escuchar."),
    ]
    tx = Transcripcion(
        audio_id="tx_ponencia_detector",
        duracion_s=20.0,
        modelo="small",
        segmentos=segs,
    )

    def clasificador_filtro(textos: list[str]) -> list[str]:
        return ["relleno", "idea", "idea", "relleno"]

    detector = DetectorSegmentos(clasificador=clasificador_filtro)

    # Respuesta mock para ResultadoPonencia con cita válida tomada del segmento retenido (id=2)
    res_mock = ResultadoPonencia(
        resumen_general="Resumen ponencia",
        ideas_clave=[],
        preguntas=[],
        mapa=MapaMental(
            titulo="Mapa",
            raiz=NodoMapa(
                id="root",
                titulo="Raiz",
                hijos=[
                    NodoMapa(
                        id="n1",
                        titulo="Publicación",
                        evidencia=Evidencia(segmento_ids=[2], inicio_s=6.0, cita="Estrategia principal de publicación."),
                    )
                ],
            ),
        ),
        modo="detector",
    )

    prov = ProveedorMock(respuestas=[res_mock])
    resultado = estructurar_transcripcion(
        tx,
        tipo_plantilla="ponencia",
        proveedor=prov,
        modo="detector",
        detector=detector,
    )

    assert isinstance(resultado, ResultadoPonencia)
    assert resultado.modo == "detector"
    # El prompt enviado al LLM solo debe contener los segmentos 2 y 3, no el 1 ni el 4 (relleno)
    prompt_enviado = prov.llamadas[0][0]
    assert "Estrategia principal de publicación." in prompt_enviado
    assert "Gestión del proceso de peer review." in prompt_enviado
    assert "Hola buenos días a todos." not in prompt_enviado
    assert "Muchas gracias por escuchar." not in prompt_enviado


def test_estructurar_modo_detector_sin_detector_cae_a_solo_llm():
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=5.0, texto="Segmento único de prueba."),
    ]
    tx = Transcripcion(
        audio_id="tx_fallback",
        duracion_s=5.0,
        modelo="small",
        segmentos=segs,
    )

    # Detector no disponible
    detector_invalido = DetectorSegmentos(modelo_id="no_existe")

    res_mock = ResultadoPonencia(
        resumen_general="Resumen",
        ideas_clave=[],
        preguntas=[],
        mapa=MapaMental(titulo="M", raiz=NodoMapa(id="r", titulo="R")),
        modo="solo_llm",
    )

    prov = ProveedorMock(respuestas=[res_mock])
    resultado = estructurar_transcripcion(
        tx,
        tipo_plantilla="ponencia",
        proveedor=prov,
        modo="detector",
        detector=detector_invalido,
    )

    # Debe caer a solo_llm
    assert resultado.modo == "solo_llm"
    prompt_enviado = prov.llamadas[0][0]
    assert "Segmento único de prueba." in prompt_enviado
