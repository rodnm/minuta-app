"""Pruebas unitarias para detección, validación y reduce de términos en inglés (T79).

Metodología test-first (S1, S2, S8, S12).
"""

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
    ResultadoEntrevista,
    Segmento,
    TerminoIngles,
    Transcripcion,
)
from minuta.estructurar import (
    validar_y_descartar_no_literales,
    estructurar_transcripcion,
)
from minuta.proveedores import ProveedorMock


def _crear_mapa_mock() -> MapaMental:
    return MapaMental(
        titulo="Mapa de prueba",
        raiz=NodoMapa(
            id="root",
            titulo="Raíz",
            hijos=[
                NodoMapa(id="h1", titulo="Rama 1"),
                NodoMapa(id="h2", titulo="Rama 2"),
            ],
        ),
    )


def test_termino_valido_aceptado():
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=4.0, texto="utilizamos JSON para serializar datos."),
    ]
    ev = Evidencia(segmento_ids=[1], inicio_s=0.0, cita="utilizamos JSON para serializar datos.")
    t = TerminoIngles(termino="JSON", transcrito="JSON", evidencia=ev)

    res = ResultadoPonencia(
        resumen_general="Resumen",
        ideas_clave=[],
        preguntas=[],
        mapa=_crear_mapa_mock(),
        terminos_ingles=[t],
    )

    res_filtrado, desc = validar_y_descartar_no_literales(res, segs)
    assert len(res_filtrado.terminos_ingles) == 1
    assert res_filtrado.terminos_ingles[0].termino == "JSON"
    assert res_filtrado.terminos_ingles[0].transcrito == "JSON"
    assert desc == 0


def test_regla_jason_a_json_aceptada():
    # 'Jason' en la transcripción literal corregido como 'JSON'
    segs = [
        Segmento(id=1, inicio_s=10.0, fin_s=15.0, texto="guardamos el modelo usando Jason en disco."),
    ]
    ev = Evidencia(segmento_ids=[1], inicio_s=10.0, cita="guardamos el modelo usando Jason en disco.")
    t = TerminoIngles(termino="JSON", transcrito="Jason", evidencia=ev)

    res = ResultadoPonencia(
        resumen_general="Resumen",
        ideas_clave=[],
        preguntas=[],
        mapa=_crear_mapa_mock(),
        terminos_ingles=[t],
    )

    res_filtrado, desc = validar_y_descartar_no_literales(res, segs)
    assert len(res_filtrado.terminos_ingles) == 1
    assert res_filtrado.terminos_ingles[0].termino == "JSON"
    assert res_filtrado.terminos_ingles[0].transcrito == "Jason"
    assert desc == 0


def test_termino_transcrito_no_en_segmento_descartado():
    # transcrito='Jason' no aparece en el texto del segmento
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=4.0, texto="esta es una clase sobre algoritmos."),
    ]
    ev = Evidencia(segmento_ids=[1], inicio_s=0.0, cita="esta es una clase sobre algoritmos.")
    t = TerminoIngles(termino="JSON", transcrito="Jason", evidencia=ev)

    res = ResultadoPonencia(
        resumen_general="Resumen",
        ideas_clave=[],
        preguntas=[],
        mapa=_crear_mapa_mock(),
        terminos_ingles=[t],
    )

    res_filtrado, desc = validar_y_descartar_no_literales(res, segs)
    assert len(res_filtrado.terminos_ingles) == 0
    assert desc == 1
    assert res_filtrado.descartados == 1


def test_termino_cita_no_contiene_transcrito_descartado():
    # El segmento contiene 'Jason', pero la cita elegida NO contiene 'Jason'
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=8.0, texto="primero definimos esquemas y luego usamos Jason."),
    ]
    ev = Evidencia(segmento_ids=[1], inicio_s=0.0, cita="primero definimos esquemas")
    t = TerminoIngles(termino="JSON", transcrito="Jason", evidencia=ev)

    res = ResultadoPonencia(
        resumen_general="Resumen",
        ideas_clave=[],
        preguntas=[],
        mapa=_crear_mapa_mock(),
        terminos_ingles=[t],
    )

    res_filtrado, desc = validar_y_descartar_no_literales(res, segs)
    assert len(res_filtrado.terminos_ingles) == 0
    assert desc == 1
    assert res_filtrado.descartados == 1


def test_reduce_elimina_duplicados_por_termino():
    # Dos bloques que detectan el mismo término (JSON) con transcripciones distintas;
    # se debe conservar solo la primera aparición.
    seg1 = Segmento(id=1, inicio_s=0.0, fin_s=350.0, texto="en el primer bloque vimos Jason.")
    seg2 = Segmento(id=2, inicio_s=610.0, fin_s=950.0, texto="en el segundo bloque revisamos JSON de nuevo.")

    tx = Transcripcion(
        audio_id="audio_test_reduce",
        duracion_s=1000.0,
        modelo="small",
        glosario=["JSON"],
        segmentos=[seg1, seg2],
    )

    ev1 = Evidencia(segmento_ids=[1], inicio_s=0.0, cita="en el primer bloque vimos Jason.")
    t1 = TerminoIngles(termino="JSON", transcrito="Jason", evidencia=ev1)

    ev2 = Evidencia(segmento_ids=[2], inicio_s=610.0, cita="en el segundo bloque revisamos JSON de nuevo.")
    t2 = TerminoIngles(termino="json", transcrito="JSON", evidencia=ev2)

    res1 = ResultadoPonencia(
        resumen_general="Resumen B1",
        ideas_clave=[],
        preguntas=[],
        mapa=_crear_mapa_mock(),
        terminos_ingles=[t1],
    )
    res2 = ResultadoPonencia(
        resumen_general="Resumen B2",
        ideas_clave=[],
        preguntas=[],
        mapa=_crear_mapa_mock(),
        terminos_ingles=[t2],
    )

    proveedor = ProveedorMock(respuestas=[res1, res2])
    res_final = estructurar_transcripcion(tx, tipo_plantilla="ponencia", proveedor=proveedor)

    assert len(res_final.terminos_ingles) == 1
    assert res_final.terminos_ingles[0].termino == "JSON"
    assert res_final.terminos_ingles[0].transcrito == "Jason"
