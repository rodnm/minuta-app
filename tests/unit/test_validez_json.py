"""Pruebas unitarias para el arnés de evaluación de validez de JSON (evaluacion/validez_json.py).

Verifica la lógica de parseo, validación de contrato Pydantic, cálculo de métricas,
umbrales de la hipótesis H6 y el modo simulado determinista.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluacion.validez_json import (
    VeredictoH6,
    evaluar_hipotesis_h6,
    cargar_bloques,
    construir_prompt,
    validar_respuesta_json,
    simular_respuesta_ollama,
    ejecutar_evaluacion,
    main as validez_main,
    UMBRAL_VALIDEZ_CONFIRMADA,
    UMBRAL_TIEMPO_CONFIRMADA_S,
    UMBRAL_VALIDEZ_FALSADA,
    UMBRAL_TIEMPO_FALSADA_S,
)
from minuta.esquemas import MapaMental, NodoMapa, Evidencia


def test_evaluar_hipotesis_h6_confirmada():
    """H6 se confirma si validez >= 95 % y tiempo < 60 s por bloque."""
    res = evaluar_hipotesis_h6(pct_validez=0.96, tiempo_promedio_s=25.4, total_bloques=5)
    assert res["veredicto"] == VeredictoH6.CONFIRMADA
    assert "Confirmada" in res["motivo"]
    assert res["pct_validez"] == 0.96
    assert res["tiempo_promedio_s"] == 25.4


def test_evaluar_hipotesis_h6_falsada_por_baja_validez():
    """H6 se falsa si validez < 85 %."""
    res = evaluar_hipotesis_h6(pct_validez=0.82, tiempo_promedio_s=40.0, total_bloques=5)
    assert res["veredicto"] == VeredictoH6.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h6_falsada_por_tiempo_excesivo():
    """H6 se falsa si tiempo promedio > 120 s por bloque."""
    res = evaluar_hipotesis_h6(pct_validez=0.98, tiempo_promedio_s=135.0, total_bloques=5)
    assert res["veredicto"] == VeredictoH6.FALSADA
    assert "Falsada" in res["motivo"]


def test_evaluar_hipotesis_h6_no_concluyente_zona_intermedia():
    """H6 es no concluyente en zonas intermedias (ej. validez 90% o tiempo 75s)."""
    # Validez intermedia (85% - 95%) con tiempo aceptable
    res1 = evaluar_hipotesis_h6(pct_validez=0.90, tiempo_promedio_s=30.0, total_bloques=5)
    assert res1["veredicto"] == VeredictoH6.NO_CONCLUYENTE

    # Validez alta pero tiempo intermedio (60s - 120s)
    res2 = evaluar_hipotesis_h6(pct_validez=0.98, tiempo_promedio_s=75.0, total_bloques=5)
    assert res2["veredicto"] == VeredictoH6.NO_CONCLUYENTE


def test_cargar_bloques_desde_archivo(tmp_path):
    """Carga segmentos y particiona en bloques de tamaño definido."""
    datos = {
        "audio_id": "test_audio",
        "duracion_s": 120.0,
        "modelo": "small",
        "segmentos": [
            {"id": i, "inicio_s": i * 10.0, "fin_s": (i + 1) * 10.0, "texto": f"Frase {i}"}
            for i in range(25)
        ],
    }
    archivo = tmp_path / "transcripcion_test.json"
    archivo.write_text(json.dumps(datos), encoding="utf-8")

    bloques = cargar_bloques(archivo, tamano_bloque=10, max_bloques=None)
    assert len(bloques) == 3
    assert len(bloques[0]["segmentos"]) == 10
    assert len(bloques[1]["segmentos"]) == 10
    assert len(bloques[2]["segmentos"]) == 5
    assert bloques[0]["inicio_s"] == 0.0
    assert bloques[0]["fin_s"] == 100.0


def test_cargar_bloques_fixtures_reales():
    """Carga los bloques desde las transcripciones reales de data/fixtures/."""
    ruta_fixtures = Path("data/fixtures")
    assert ruta_fixtures.exists(), "data/fixtures debe existir"

    bloques = cargar_bloques(ruta_fixtures, tamano_bloque=10, max_bloques=3)
    assert len(bloques) == 3
    for b in bloques:
        assert "id_bloque" in b
        assert "segmentos" in b
        assert len(b["segmentos"]) > 0
        assert b["inicio_s"] >= 0.0


def test_construir_prompt():
    """El prompt incluye las instrucciones y el texto de los segmentos con sus marcas."""
    bloque = {
        "id_bloque": "bloque_0",
        "inicio_s": 0.0,
        "fin_s": 30.0,
        "segmentos": [
            {"id": 1, "inicio_s": 0.0, "fin_s": 15.0, "texto": "Primera idea importante."},
            {"id": 2, "inicio_s": 15.0, "fin_s": 30.0, "texto": "Segunda idea crucial."},
        ],
    }
    prompt = construir_prompt(bloque)
    assert "MapaMental" in prompt or "raiz" in prompt
    assert "Primera idea importante." in prompt
    assert "Segunda idea crucial." in prompt
    assert "inicio_s" in prompt


def test_validar_respuesta_json_valido():
    """Valida un JSON válido y conforme al contrato MapaMental."""
    json_valido = json.dumps({
        "titulo": "Mapa de Ponencia",
        "raiz": {
            "id": "raiz",
            "titulo": "Tema Central",
            "resumen": "Resumen global del bloque",
            "evidencia": None,
            "hijos": [
                {
                    "id": "nodo_1",
                    "titulo": "Subtema A",
                    "resumen": "Detalle de A",
                    "evidencia": {
                        "segmento_ids": [1],
                        "inicio_s": 10.0,
                        "cita": "cita literal de prueba",
                    },
                    "hijos": [],
                }
            ],
        },
    })

    res = validar_respuesta_json(json_valido)
    assert res["es_json_valido"] is True
    assert res["es_pydantic_valido"] is True
    assert res["error"] is None
    assert isinstance(res["mapa"], MapaMental)
    assert res["mapa"].raiz.titulo == "Tema Central"


def test_validar_respuesta_json_invalido_sintaxis():
    """Detecta JSON con error de sintaxis."""
    json_malformado = "{'titulo': 'Invalido por comillas simples y sin cerrar'"
    res = validar_respuesta_json(json_malformado)
    assert res["es_json_valido"] is False
    assert res["es_pydantic_valido"] is False
    assert res["mapa"] is None
    assert res["error"] is not None


def test_validar_respuesta_json_valido_pero_pydantic_invalido():
    """Detecta JSON con sintaxis correcta pero campos faltantes o inválidos para el esquema."""
    json_esquema_invalido = json.dumps({
        "titulo": "Solo titulo sin raiz",
        "otra_cosa": 123,
    })
    res = validar_respuesta_json(json_esquema_invalido)
    assert res["es_json_valido"] is True
    assert res["es_pydantic_valido"] is False
    assert res["mapa"] is None
    assert "raiz" in res["error"]


def test_validar_respuesta_con_marcado_markdown():
    """Limpia bloques de código ```json ... ``` devueltos por el LLM."""
    raw = """```json
    {
      "titulo": "Mapa con markdown",
      "raiz": {
        "id": "raiz",
        "titulo": "Raiz",
        "evidencia": null,
        "hijos": []
      }
    }
    ```"""
    res = validar_respuesta_json(raw)
    assert res["es_json_valido"] is True
    assert res["es_pydantic_valido"] is True
    assert res["mapa"] is not None


def test_simular_respuesta_ollama_determinista():
    """La respuesta simulada genera un MapaMental válido con citas literales de los segmentos."""
    bloque = {
        "id_bloque": "bloque_test",
        "inicio_s": 0.0,
        "fin_s": 30.0,
        "segmentos": [
            {"id": 1, "inicio_s": 0.0, "fin_s": 15.0, "texto": "Publicar en un journal indexado."},
            {"id": 2, "inicio_s": 15.0, "fin_s": 30.0, "texto": "Revisión por pares con peer review."},
        ],
    }
    sim = simular_respuesta_ollama(bloque, seed=42)
    assert "respuesta" in sim
    assert sim["duracion_s"] > 0

    val = validar_respuesta_json(sim["respuesta"])
    assert val["es_json_valido"] is True
    assert val["es_pydantic_valido"] is True
    assert val["mapa"] is not None


def test_ejecutar_evaluacion_modo_simulado():
    """Ejecución de evaluación completa en modo simulado."""
    ruta_fixtures = Path("data/fixtures")
    bloques = cargar_bloques(ruta_fixtures, tamano_bloque=10, max_bloques=3)

    resultado = ejecutar_evaluacion(
        bloques=bloques,
        proveedor="ollama",
        modelo="qwen3:4b",
        simulado=True,
    )

    assert resultado["total_bloques"] == 3
    assert resultado["total_json_validos"] == 3
    assert resultado["total_pydantic_validos"] == 3
    assert resultado["pct_validez"] == 1.0
    assert resultado["tiempo_promedio_s"] < 60.0
    assert resultado["veredicto_h6"]["veredicto"] == VeredictoH6.CONFIRMADA
    assert len(resultado["detalles_bloques"]) == 3


def test_main_cli_simulado(tmp_path):
    """Prueba la ejecución de la función main con argumentos de línea de comandos en modo simulado."""
    archivo_salida = tmp_path / "reporte_h6.json"
    codigo = validez_main([
        "--simulado",
        "--bloques", "data/fixtures/",
        "--n", "2",
        "--salida", str(archivo_salida),
    ])
    assert codigo == 0
    assert archivo_salida.exists()

    contenido = json.loads(archivo_salida.read_text(encoding="utf-8"))
    assert contenido["total_bloques"] == 2
    assert contenido["pct_validez"] == 1.0
    assert "veredicto_h6" in contenido


def test_main_cli_ruta_invalida():
    """Retorna código de error cuando la ruta de bloques no existe."""
    codigo = validez_main(["--bloques", "ruta_inexistente_de_prueba/"])
    assert codigo == 1

