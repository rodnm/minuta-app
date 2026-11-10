"""Pruebas unitarias para proveedores LLM y estructuración Map-Reduce de Minuta.

Metodología test-first (T11, S2, S15, H9).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import pytest
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from minuta.esquemas import (
    Acuerdo,
    Evidencia,
    MapaMental,
    NodoMapa,
    Pendiente,
    ResultadoEntrevista,
    ResultadoPonencia,
    ResultadoReunion,
    Segmento,
    Tarea,
    Tema,
    Transcripcion,
)
from minuta.estructurar import (
    estructurar_transcripcion,
    particionar_en_bloques,
    validar_y_descartar_no_literales,
)
from minuta.proveedores import (
    ErrorProveedorLLM,
    ProveedorGemini,
    ProveedorLLM,
    ProveedorMock,
    ProveedorOllama,
)

FIXTURES_DIR = ROOT_DIR / "data" / "fixtures"


# ---------------------------------------------------------------------------
# 1. Pruebas de Proveedores LLM
# ---------------------------------------------------------------------------

class EsquemaPrueba(BaseModel):
    mensaje: str
    numero: int


def test_proveedor_mock_retorna_objeto_y_registra_llamadas():
    respuesta_esperada = EsquemaPrueba(mensaje="Hola", numero=42)
    mock = ProveedorMock(respuestas=[respuesta_esperada])

    resultado = mock.generar_estructurado("Prompt de prueba", EsquemaPrueba)

    assert isinstance(resultado, EsquemaPrueba)
    assert resultado.mensaje == "Hola"
    assert resultado.numero == 42
    assert len(mock.llamadas) == 1
    assert mock.llamadas[0][0] == "Prompt de prueba"
    assert mock.llamadas[0][1] is EsquemaPrueba


def test_proveedor_mock_desde_dict_y_json_str():
    mock_dict = ProveedorMock(respuestas=[{"mensaje": "Desde dict", "numero": 10}])
    res_dict = mock_dict.generar_estructurado("P1", EsquemaPrueba)
    assert res_dict.mensaje == "Desde dict"

    mock_json = ProveedorMock(respuestas=['{"mensaje": "Desde json", "numero": 20}'])
    res_json = mock_json.generar_estructurado("P2", EsquemaPrueba)
    assert res_json.numero == 20


def test_proveedor_mock_sin_respuestas_lanza_error():
    mock = ProveedorMock(respuestas=[])
    with pytest.raises(ErrorProveedorLLM, match="No hay más respuestas"):
        mock.generar_estructurado("Prompt", EsquemaPrueba)


def test_proveedor_gemini_sin_api_key_lanza_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("minuta.proveedores._obtener_gemini_api_key", lambda: None)
    with pytest.raises(ErrorProveedorLLM, match="GEMINI_API_KEY"):
        ProveedorGemini(api_key=None)


def test_proveedor_ollama_error_conexion_host_invalido():
    proveedor = ProveedorOllama(host="http://localhost:59999", timeout=1.0)
    with pytest.raises(ErrorProveedorLLM):
        proveedor.generar_estructurado("Prompt", EsquemaPrueba)


# ---------------------------------------------------------------------------
# 2. Pruebas de Partición en Bloques (~10 minutos)
# ---------------------------------------------------------------------------

def test_particion_un_solo_bloque_menor_o_igual_a_600s():
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=200.0, texto="Segmento 1"),
        Segmento(id=2, inicio_s=200.0, fin_s=400.0, texto="Segmento 2"),
        Segmento(id=3, inicio_s=400.0, fin_s=600.0, texto="Segmento 3"),
    ]
    tx = Transcripcion(
        audio_id="audio_corto",
        duracion_s=600.0,
        modelo="small",
        segmentos=segs,
    )

    bloques = particionar_en_bloques(tx.segmentos, max_duracion_bloque_s=600.0)
    assert len(bloques) == 1
    assert len(bloques[0]) == 3


def test_particion_multiples_bloques_acumulando_duracion():
    # 4 segmentos de 200 segundos cada uno = 800 segundos total
    # Bloque 1: segs 0, 1, 2 (acumula 200+200+200=600s)
    # Bloque 2: seg 3 (200s)
    segs = [
        Segmento(id=1, inicio_s=0.0, fin_s=200.0, texto="Parte 1"),
        Segmento(id=2, inicio_s=200.0, fin_s=400.0, texto="Parte 2"),
        Segmento(id=3, inicio_s=400.0, fin_s=600.0, texto="Parte 3"),
        Segmento(id=4, inicio_s=600.0, fin_s=800.0, texto="Parte 4"),
    ]
    bloques = particionar_en_bloques(segs, max_duracion_bloque_s=600.0)
    assert len(bloques) == 2
    assert len(bloques[0]) == 3
    assert len(bloques[1]) == 1
    assert bloques[1][0].id == 4


def test_particion_transcripcion_vacia():
    bloques = particionar_en_bloques([], max_duracion_bloque_s=600.0)
    assert bloques == []


# ---------------------------------------------------------------------------
# 3. Pruebas de Descarte Estricto de Citas No Literales
# ---------------------------------------------------------------------------

def test_descarte_citas_no_literales_incrementa_contador():
    segmentos = [
        Segmento(id=1, inicio_s=0.0, fin_s=10.0, texto="El peer review es un proceso riguroso."),
        Segmento(id=2, inicio_s=10.0, fin_s=20.0, texto="Debemos someter el paper antes del deadline."),
    ]

    raiz = NodoMapa(
        id="root",
        titulo="Raíz",
        hijos=[
            NodoMapa(
                id="n1",
                titulo="Nodo Válido",
                evidencia=Evidencia(segmento_ids=[1], inicio_s=2.0, cita="peer review es un proceso"),
            ),
            NodoMapa(
                id="n2_invalido",
                titulo="Nodo Alucinado",
                # Esta cita NO existe en los segmentos
                evidencia=Evidencia(segmento_ids=[1], inicio_s=5.0, cita="esta cita fue inventada por el LLM"),
            ),
        ],
    )
    mapa = MapaMental(titulo="Mapa de Prueba", raiz=raiz)

    # Tarea válida y tarea con cita inventada
    tarea_valida = Tarea(
        descripcion="Someter paper",
        evidencia=Evidencia(segmento_ids=[2], inicio_s=12.0, cita="someter el paper antes del deadline"),
    )
    tarea_invalida = Tarea(
        descripcion="Comprar licencias",
        evidencia=Evidencia(segmento_ids=[2], inicio_s=15.0, cita="comprar software privativo en la tienda"),
    )

    resultado_crudo = ResultadoReunion(
        resumen_general="Resumen",
        temas=[],
        acuerdos=[],
        tareas=[tarea_valida, tarea_invalida],
        pendientes=[],
        mapa=mapa,
        descartados=0,
        modo="solo_llm",
    )

    resultado_filtrado, descartados = validar_y_descartar_no_literales(resultado_crudo, segmentos)

    # Se debieron descartar 1 nodo del mapa y 1 tarea -> total 2 descartados
    assert descartados == 2
    assert resultado_filtrado.descartados == 2

    # El mapa filtrado solo debe conservar el nodo con cita literal
    assert len(resultado_filtrado.mapa.raiz.hijos) == 1
    assert resultado_filtrado.mapa.raiz.hijos[0].id == "n1"

    # La lista de tareas solo conserva la tarea válida
    assert len(resultado_filtrado.tareas) == 1
    assert resultado_filtrado.tareas[0].descripcion == "Someter paper"


# ---------------------------------------------------------------------------
# 4. Pruebas de Estructuración con las 3 Plantillas y Fixtures
# ---------------------------------------------------------------------------

def test_estructurar_ponencia_con_fixture():
    ruta_tx = FIXTURES_DIR / "transcripcion_ponencia.json"
    ruta_res = FIXTURES_DIR / "resultado_ponencia.json"

    tx = Transcripcion.model_validate_json(ruta_tx.read_text(encoding="utf-8"))
    res_esperado = ResultadoPonencia.model_validate_json(ruta_res.read_text(encoding="utf-8"))

    mock = ProveedorMock(respuestas=[res_esperado])
    resultado = estructurar_transcripcion(tx, tipo_plantilla="ponencia", proveedor=mock, modo="solo_llm")

    assert isinstance(resultado, ResultadoPonencia)
    assert resultado.modo == "solo_llm"
    assert resultado.descartados == 0
    assert len(resultado.ideas_clave) >= 2
    assert len(resultado.preguntas) >= 1

    # Comprobar árbol y to_markdown()
    md = resultado.mapa.to_markdown()
    assert md.startswith("# ")
    assert "## " in md
    assert "[mm:ss]" not in md  # La etiqueta debe tener números reales, no el literal [mm:ss]
    assert "[" in md and ":" in md and "]" in md


def test_estructurar_reunion_con_fixture():
    ruta_tx = FIXTURES_DIR / "transcripcion_reunion.json"
    ruta_res = FIXTURES_DIR / "resultado_reunion.json"

    tx = Transcripcion.model_validate_json(ruta_tx.read_text(encoding="utf-8"))
    res_esperado = ResultadoReunion.model_validate_json(ruta_res.read_text(encoding="utf-8"))

    mock = ProveedorMock(respuestas=[res_esperado])
    resultado = estructurar_transcripcion(tx, tipo_plantilla="reunion", proveedor=mock, modo="detector")

    assert isinstance(resultado, ResultadoReunion)
    assert resultado.modo == "detector"
    assert resultado.descartados == 0
    assert len(resultado.acuerdos) >= 1
    assert len(resultado.tareas) >= 1
    assert resultado.mapa is not None


def test_estructurar_entrevista_con_fixture():
    ruta_tx = FIXTURES_DIR / "transcripcion_entrevista.json"
    ruta_res = FIXTURES_DIR / "resultado_entrevista.json"

    tx = Transcripcion.model_validate_json(ruta_tx.read_text(encoding="utf-8"))
    res_esperado = ResultadoEntrevista.model_validate_json(ruta_res.read_text(encoding="utf-8"))

    mock = ProveedorMock(respuestas=[res_esperado])
    resultado = estructurar_transcripcion(tx, tipo_plantilla="entrevista", proveedor=mock, modo="solo_llm")

    assert isinstance(resultado, ResultadoEntrevista)
    assert len(resultado.libro) >= 1
    assert len(resultado.fragmentos) >= 1
    assert len(resultado.resumen_por_codigo) >= 1
    assert resultado.descartados == 0


# ---------------------------------------------------------------------------
# 5. Prueba de Map-Reduce con Múltiples Bloques
# ---------------------------------------------------------------------------

def test_map_reduce_multiples_bloques_agrega_resultados():
    # Creamos una transcripción de 1200 segundos (2 bloques de ~600s)
    segs_bloque1 = [
        Segmento(id=1, inicio_s=0.0, fin_s=300.0, texto="Primera mitad sobre publicaciones."),
        Segmento(id=2, inicio_s=300.0, fin_s=600.0, texto="Proceso de peer review detallado."),
    ]
    segs_bloque2 = [
        Segmento(id=3, inicio_s=600.0, fin_s=900.0, texto="Segunda mitad sobre financiamiento."),
        Segmento(id=4, inicio_s=900.0, fin_s=1200.0, texto="Postulación a los grants nacionales."),
    ]
    tx = Transcripcion(
        audio_id="ponencia_larga",
        duracion_s=1200.0,
        modelo="small",
        segmentos=segs_bloque1 + segs_bloque2,
    )

    # Respuestas simuladas para el bloque 1 y el bloque 2
    res_b1 = ResultadoPonencia(
        resumen_general="Bloque 1 de publicaciones.",
        ideas_clave=[
            Tema(
                titulo="Publicaciones",
                resumen="Estrategias",
                evidencias=[Evidencia(segmento_ids=[1], inicio_s=10.0, cita="Primera mitad sobre publicaciones.")],
            )
        ],
        preguntas=[],
        mapa=MapaMental(
            titulo="Mapa B1",
            raiz=NodoMapa(
                id="root_b1",
                titulo="Eje 1",
                hijos=[
                    NodoMapa(
                        id="n1",
                        titulo="Tema A",
                        evidencia=Evidencia(segmento_ids=[2], inicio_s=310.0, cita="Proceso de peer review"),
                    )
                ],
            ),
        ),
        descartados=0,
    )

    res_b2 = ResultadoPonencia(
        resumen_general="Bloque 2 de financiamiento.",
        ideas_clave=[
            Tema(
                titulo="Financiamiento",
                resumen="Grants",
                evidencias=[Evidencia(segmento_ids=[4], inicio_s=910.0, cita="Postulación a los grants")],
            )
        ],
        preguntas=[
            Pendiente(
                descripcion="Monto del grant",
                evidencia=Evidencia(segmento_ids=[4], inicio_s=920.0, cita="grants nacionales."),
            )
        ],
        mapa=MapaMental(
            titulo="Mapa B2",
            raiz=NodoMapa(
                id="root_b2",
                titulo="Eje 2",
                hijos=[
                    NodoMapa(
                        id="n2",
                        titulo="Tema B",
                        evidencia=Evidencia(segmento_ids=[3], inicio_s=610.0, cita="financiamiento."),
                    )
                ],
            ),
        ),
        descartados=0,
    )

    mock = ProveedorMock(respuestas=[res_b1, res_b2])
    resultado = estructurar_transcripcion(tx, tipo_plantilla="ponencia", proveedor=mock, modo="solo_llm")

    # Verifica que el Map ejecutó 2 llamadas (una por bloque)
    assert len(mock.llamadas) == 2

    # Verifica que el Reduce unificó los resultados
    assert isinstance(resultado, ResultadoPonencia)
    assert "Bloque 1" in resultado.resumen_general
    assert "Bloque 2" in resultado.resumen_general
    assert len(resultado.ideas_clave) == 2
    assert len(resultado.preguntas) == 1

    # El árbol unificado debe contener ramas de ambos bloques bajo la raíz común
    hijos_raiz = resultado.mapa.raiz.hijos
    assert len(hijos_raiz) == 2
    titulos_hijos = {h.titulo for h in hijos_raiz}
    assert "Tema A" in titulos_hijos
    assert "Tema B" in titulos_hijos
