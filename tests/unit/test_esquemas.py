"""Pruebas unitarias para el contrato de datos Pydantic v2 y fixtures de Minuta.

Metodología test-first (T01, S1, S2, S15).
"""

import json
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from minuta.esquemas import (
    Segmento,
    Transcripcion,
    Evidencia,
    NodoMapa,
    MapaMental,
    Tarea,
    Acuerdo,
    Pendiente,
    Tema,
    CodigoLibro,
    FragmentoCodificado,
    ResultadoPonencia,
    ResultadoReunion,
    ResultadoEntrevista,
    validar_evidencia_literal,
)


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"


# ---------------------------------------------------------------------------
# 1. Pruebas de Segmento y Transcripcion
# ---------------------------------------------------------------------------

def test_segmento_valido():
    seg = Segmento(id=1, inicio_s=0.0, fin_s=3.5, texto="Bienvenidos a la ponencia.")
    assert seg.id == 1
    assert seg.inicio_s == 0.0
    assert seg.fin_s == 3.5
    assert seg.texto == "Bienvenidos a la ponencia."


def test_segmento_invalido_fin_menor_que_inicio():
    with pytest.raises(ValidationError):
        Segmento(id="s1", inicio_s=10.0, fin_s=5.0, texto="Texto con tiempos inconsistentes.")


def test_segmento_invalido_inicio_negativo():
    with pytest.raises(ValidationError):
        Segmento(id="s2", inicio_s=-1.0, fin_s=2.0, texto="Tiempo negativo.")


def test_transcripcion_valida():
    seg1 = Segmento(id=1, inicio_s=0.0, fin_s=4.0, texto="Hola a todos.")
    seg2 = Segmento(id=2, inicio_s=4.0, fin_s=8.0, texto="Hoy hablaremos del journal.")
    tx = Transcripcion(
        audio_id="audio_001",
        duracion_s=8.0,
        modelo="small",
        glosario=["journal", "paper"],
        segmentos=[seg1, seg2],
    )
    assert tx.audio_id == "audio_001"
    assert tx.duracion_s == 8.0
    assert len(tx.segmentos) == 2
    assert "journal" in tx.glosario


# ---------------------------------------------------------------------------
# 2. Pruebas de Evidencia y helper validar_evidencia_literal
# ---------------------------------------------------------------------------

def test_evidencia_valida():
    ev = Evidencia(segmento_ids=[1], inicio_s=4.5, cita="Hoy hablaremos del journal.")
    assert ev.segmento_ids == [1]
    assert ev.inicio_s == 4.5
    assert ev.cita == "Hoy hablaremos del journal."


def test_evidencia_invalida_cita_vacia():
    with pytest.raises(ValidationError):
        Evidencia(segmento_ids=[1], inicio_s=0.0, cita="   ")


def test_evidencia_invalida_segmento_ids_vacio():
    with pytest.raises(ValidationError):
        Evidencia(segmento_ids=[], inicio_s=0.0, cita="Cita sin segmentos asociados.")


def test_validar_evidencia_literal_subcadena_exacta():
    seg = Segmento(id=1, inicio_s=0.0, fin_s=5.0, texto="Presentamos un paper en la conferencia Scopus.")
    assert validar_evidencia_literal("paper en la conferencia", [seg]) is True
    assert validar_evidencia_literal("Scopus.", [seg]) is True


def test_validar_evidencia_literal_falsa_o_alterada():
    seg = Segmento(id=1, inicio_s=0.0, fin_s=5.0, texto="Presentamos un paper en la conferencia Scopus.")
    # Paráfrasis no literal
    assert validar_evidencia_literal("un artículo en la conferencia", [seg]) is False
    # Modificación de una palabra
    assert validar_evidencia_literal("paper sobre la conferencia", [seg]) is False
    # Segmentos vacíos
    assert validar_evidencia_literal("paper", []) is False


def test_validar_evidencia_literal_entre_multiples_segmentos():
    seg1 = Segmento(id=1, inicio_s=0.0, fin_s=4.0, texto="Debemos revisar el peer")
    seg2 = Segmento(id=2, inicio_s=4.0, fin_s=8.0, texto="review antes del deadline.")
    # Cita que abarca el final del primero y el inicio del segundo
    assert validar_evidencia_literal("peer review antes", [seg1, seg2]) is True


# ---------------------------------------------------------------------------
# 3. Pruebas de NodoMapa y MapaMental (con to_markdown y tag [mm:ss])
# ---------------------------------------------------------------------------

def test_nodo_mapa_tiempo_tag():
    ev = Evidencia(segmento_ids=[1], inicio_s=125.0, cita="Revisión de literatura.")
    nodo = NodoMapa(id="n1", titulo="Estado del arte", evidencia=ev)
    # 125 segundos = 2 minutos 5 segundos -> [02:05]
    assert nodo.tiempo_tag() == "[02:05]"

    nodo_raiz = NodoMapa(id="root", titulo="Mapa General", evidencia=None)
    assert nodo_raiz.tiempo_tag() is None


def test_mapa_mental_to_markdown():
    raiz = NodoMapa(
        id="root",
        titulo="Seminario de Investigación",
        evidencia=None,
        hijos=[
            NodoMapa(
                id="n1",
                titulo="Publicaciones en Journals",
                resumen="Estrategias para Q1 y Q2.",
                evidencia=Evidencia(segmento_ids=[1], inicio_s=65.0, cita="Publicaciones en Journals Q1."),
                hijos=[
                    NodoMapa(
                        id="n1_1",
                        titulo="Proceso de Peer Review",
                        evidencia=Evidencia(segmento_ids=[2], inicio_s=150.0, cita="El peer review toma meses."),
                    )
                ],
            ),
            NodoMapa(
                id="n2",
                titulo="Fondos y Grants",
                evidencia=Evidencia(segmento_ids=[3], inicio_s=300.0, cita="Postulación al grant de Concytec."),
            ),
        ],
    )
    mapa = MapaMental(titulo="Seminario de Investigación", raiz=raiz)
    md = mapa.to_markdown()

    # Comprobaciones de formato Markdown jerárquico
    assert "# Seminario de Investigación" in md
    assert "## Publicaciones en Journals [01:05]" in md
    assert "### Proceso de Peer Review [02:30]" in md
    assert "## Fondos y Grants [05:00]" in md
    assert "Estrategias para Q1 y Q2." in md


# ---------------------------------------------------------------------------
# 4. Pruebas de Modelos de Plantillas
# ---------------------------------------------------------------------------

def test_modelos_de_plantillas():
    ev = Evidencia(segmento_ids=[1], inicio_s=10.0, cita="Enviar el draft mañana.")

    tarea = Tarea(descripcion="Enviar borrador del paper", responsable="Rodrigo", fecha_limite="2026-11-15", evidencia=ev)
    assert tarea.responsable == "Rodrigo"

    acuerdo = Acuerdo(descripcion="Aprobar presupuesto de software", evidencia=ev)
    assert acuerdo.descripcion == "Aprobar presupuesto de software"

    pendiente = Pendiente(descripcion="Consultar costo de publicación APC", evidencia=ev)
    assert pendiente.descripcion == "Consultar costo de publicación APC"

    tema = Tema(titulo="Metodología", resumen="Discusión sobre el pipeline.", evidencias=[ev])
    assert len(tema.evidencias) == 1

    libro = CodigoLibro(codigo="BARR_TIEMPO", descripcion="Barreras de tiempo para investigar")
    assert libro.codigo == "BARR_TIEMPO"

    frag = FragmentoCodificado(codigo="BARR_TIEMPO", evidencia=ev, nota="Docente con sobrecarga horaria.")
    assert frag.nota == "Docente con sobrecarga horaria."


# ---------------------------------------------------------------------------
# 5. Pruebas de Carga y Validación de Fixtures de las 3 Plantillas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "nombre_tx,modelo_tx_cls,nombre_res,modelo_res_cls",
    [
        ("transcripcion_ponencia.json", Transcripcion, "resultado_ponencia.json", ResultadoPonencia),
        ("transcripcion_reunion.json", Transcripcion, "resultado_reunion.json", ResultadoReunion),
        ("transcripcion_entrevista.json", Transcripcion, "resultado_entrevista.json", ResultadoEntrevista),
    ],
)
def test_fixtures_esquemas_y_estructura(nombre_tx, modelo_tx_cls, nombre_res, modelo_res_cls):
    ruta_tx = FIXTURES_DIR / nombre_tx
    ruta_res = FIXTURES_DIR / nombre_res

    assert ruta_tx.exists(), f"No existe el archivo {ruta_tx}"
    assert ruta_res.exists(), f"No existe el archivo {ruta_res}"

    tx_data = json.loads(ruta_tx.read_text(encoding="utf-8"))
    res_data = json.loads(ruta_res.read_text(encoding="utf-8"))

    tx_obj = modelo_tx_cls.model_validate(tx_data)
    res_obj = modelo_res_cls.model_validate(res_data)

    # Cada transcripción de prueba debe tener al menos 35 segmentos (~40 segmentos requeridos)
    assert len(tx_obj.segmentos) >= 35, f"{nombre_tx} tiene menos de 35 segmentos: {len(tx_obj.segmentos)}"

    # Verificar jerga ES-EN de investigación en los textos de transcripción
    texto_total = " ".join(s.texto for s in tx_obj.segmentos).lower()
    terminos_esperados = ["journal", "paper", "peer review", "deadline", "grant", "scopus"]
    coincidencias = [t for t in terminos_esperados if t in texto_total]
    assert len(coincidencias) >= 3, f"Pocos términos de investigación en {nombre_tx}: {coincidencias}"

    # El resultado debe tener un mapa mental válido
    assert res_obj.mapa is not None
    assert res_obj.mapa.raiz is not None
    assert len(res_obj.mapa.raiz.hijos) >= 2


# ---------------------------------------------------------------------------
# 6. Verificación exhaustiva: 100% de citas en fixtures deben ser literales
# ---------------------------------------------------------------------------

def _extraer_evidencias_de_objeto(obj) -> list[Evidencia]:
    evidencias = []
    if isinstance(obj, Evidencia):
        evidencias.append(obj)
    elif hasattr(obj, "__dict__"):
        for val in obj.__dict__.values():
            evidencias.extend(_extraer_evidencias_de_objeto(val))
    elif isinstance(obj, list):
        for item in obj:
            evidencias.extend(_extraer_evidencias_de_objeto(item))
    elif isinstance(obj, dict):
        for val in obj.values():
            evidencias.extend(_extraer_evidencias_de_objeto(val))
    return evidencias


@pytest.mark.parametrize(
    "nombre_tx,nombre_res,modelo_res_cls",
    [
        ("transcripcion_ponencia.json", "resultado_ponencia.json", ResultadoPonencia),
        ("transcripcion_reunion.json", "resultado_reunion.json", ResultadoReunion),
        ("transcripcion_entrevista.json", "resultado_entrevista.json", ResultadoEntrevista),
    ],
)
def test_fixtures_todas_las_citas_son_literales(nombre_tx, nombre_res, modelo_res_cls):
    ruta_tx = FIXTURES_DIR / nombre_tx
    ruta_res = FIXTURES_DIR / nombre_res

    tx = Transcripcion.model_validate_json(ruta_tx.read_text(encoding="utf-8"))
    res = modelo_res_cls.model_validate_json(ruta_res.read_text(encoding="utf-8"))

    mapa_segmentos = {s.id: s for s in tx.segmentos}
    todas_evidencias = _extraer_evidencias_de_objeto(res)

    assert len(todas_evidencias) > 0, f"No se encontraron evidencias en {nombre_res}"

    for ev in todas_evidencias:
        segs_referenciados = [mapa_segmentos[sid] for sid in ev.segmento_ids if sid in mapa_segmentos]
        assert len(segs_referenciados) == len(ev.segmento_ids), (
            f"Segmentos citados {ev.segmento_ids} no encontrados completamente en {nombre_tx}"
        )
        es_literal = validar_evidencia_literal(ev.cita, segs_referenciados)
        assert es_literal, (
            f"Cita no literal en {nombre_res}: '{ev.cita}' no encontrada en segmentos {ev.segmento_ids}"
        )
