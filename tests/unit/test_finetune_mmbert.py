"""Pruebas unitarias para el módulo de fine-tuning de mmBERT-small.

Metodología test-first (T12, S4, H4).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from entrenamiento.finetune_mmbert_cpu import (
    CLASES_ESTANDAR,
    ID2LABEL,
    LABEL2ID,
    calcular_pesos_clase,
    cargar_dataset_sintetico,
    construir_parser_cli,
    entrenar_cpu,
)

RUTA_SINTETICOS = ROOT_DIR / "entrenamiento" / "datos" / "sinteticos_entrenamiento.json"


# ---------------------------------------------------------------------------
# 1. Pruebas de Mapeo de Etiquetas (5 clases estándar)
# ---------------------------------------------------------------------------

def test_clases_y_mapeos_biyectivos():
    assert len(CLASES_ESTANDAR) == 5
    esperadas = {"idea", "tarea", "acuerdo", "pregunta", "relleno"}
    assert set(CLASES_ESTANDAR) == esperadas

    # Validar que LABEL2ID e ID2LABEL sean inversas exactas
    assert len(LABEL2ID) == 5
    assert len(ID2LABEL) == 5
    for clase, idx in LABEL2ID.items():
        assert ID2LABEL[idx] == clase


# ---------------------------------------------------------------------------
# 2. Pruebas de Carga de Dataset Sintético
# ---------------------------------------------------------------------------

def test_cargar_dataset_sintetico_desde_archivo_real():
    assert RUTA_SINTETICOS.exists(), f"No existe {RUTA_SINTETICOS}"
    ejemplos = cargar_dataset_sintetico(RUTA_SINTETICOS)

    assert len(ejemplos) > 500, f"Se esperaban más de 500 segmentos, se obtuvieron {len(ejemplos)}"
    clases_encontradas = set()

    for ex in ejemplos:
        assert "texto" in ex and isinstance(ex["texto"], str)
        assert len(ex["texto"].strip()) > 0
        assert "etiqueta" in ex and ex["etiqueta"] in CLASES_ESTANDAR
        clases_encontradas.add(ex["etiqueta"])

    # Todas las 5 clases deben estar presentes en el dataset
    assert clases_encontradas == set(CLASES_ESTANDAR)


def test_cargar_dataset_sintetico_archivo_temporal(tmp_path):
    data_mock = {
        "conversaciones": [
            {
                "id": "conv_01",
                "segmentos": [
                    {"texto": "Debemos enviar el draft hoy.", "etiqueta": "tarea"},
                    {"texto": "Buenos días a todos.", "etiqueta": "relleno"},
                    {"texto": "Texto sin etiqueta válida", "etiqueta": "desconocida"},
                    {"texto": "   ", "etiqueta": "idea"},  # Texto vacío a descartar
                ],
            }
        ]
    }
    p = tmp_path / "datos_test.json"
    p.write_text(json.dumps(data_mock), encoding="utf-8")

    cargados = cargar_dataset_sintetico(p)
    # Solo deben cargarse los 2 válidos (tarea y relleno)
    assert len(cargados) == 2
    assert cargados[0]["etiqueta"] == "tarea"
    assert cargados[1]["etiqueta"] == "relleno"


def test_cargar_dataset_sintetico_archivo_inexistente():
    with pytest.raises(FileNotFoundError):
        cargar_dataset_sintetico("ruta/inexistente/dataset.json")


# ---------------------------------------------------------------------------
# 3. Pruebas de Cálculo de Pesos de Clase
# ---------------------------------------------------------------------------

def test_calcular_pesos_clase_desbalance():
    # 80 ideas, 10 tareas, 10 rellenos
    etiquetas = ["idea"] * 80 + ["tarea"] * 10 + ["relleno"] * 10
    pesos = calcular_pesos_clase(etiquetas)

    assert "idea" in pesos
    assert "tarea" in pesos
    assert "relleno" in pesos

    # La clase minoritaria (tarea) debe tener significativamente mayor peso que la mayoritaria (idea)
    assert pesos["tarea"] > pesos["idea"]
    assert pesos["relleno"] > pesos["idea"]
    assert pytest.approx(pesos["tarea"], rel=1e-3) == pesos["relleno"]


def test_calcular_pesos_clase_balanceado_uniforme():
    # 20 de cada clase
    etiquetas = ["idea"] * 20 + ["tarea"] * 20 + ["acuerdo"] * 20 + ["pregunta"] * 20 + ["relleno"] * 20
    pesos = calcular_pesos_clase(etiquetas)

    for c in CLASES_ESTANDAR:
        assert pytest.approx(pesos[c], rel=1e-3) == 1.0


def test_calcular_pesos_clase_vacio():
    pesos = calcular_pesos_clase([])
    assert pesos == {}


# ---------------------------------------------------------------------------
# 4. Pruebas de Parser CLI y Opciones
# ---------------------------------------------------------------------------

def test_construir_parser_cli():
    parser = construir_parser_cli()
    args = parser.parse_args([
        "--datos", "mi_dataset.json",
        "--salida-modelo", "mi_modelo_salida",
        "--prueba-rapida",
        "--epochs", "2",
        "--batch-size", "4",
        "--lr", "5e-5",
        "--semilla", "123",
    ])

    assert args.datos == "mi_dataset.json"
    assert args.salida_modelo == "mi_modelo_salida"
    assert args.prueba_rapida is True
    assert args.epochs == 2
    assert args.batch_size == 4
    assert args.lr == 5e-5
    assert args.semilla == 123


def test_parser_cli_valores_por_defecto():
    parser = construir_parser_cli()
    args = parser.parse_args([])

    assert "sinteticos_entrenamiento.json" in str(args.datos)
    assert "minuta-detector-mmbert-small" in str(args.salida_modelo)
    assert args.prueba_rapida is False
    assert args.epochs == 3
    assert args.semilla == 42


# ---------------------------------------------------------------------------
# 5. Pruebas Defensivas sin PyTorch / Entorno CPU
# ---------------------------------------------------------------------------

def test_entrenar_cpu_comportamiento_sin_torch_o_transformers(monkeypatch):
    # Si torch o transformers no están instalados, entrenar_cpu debe reportar un error claro
    monkeypatch.setattr("entrenamiento.finetune_mmbert_cpu._TORCH_DISPONIBLE", False)

    with pytest.raises(RuntimeError, match="PyTorch o Transformers no están instalados"):
        entrenar_cpu(
            datos=RUTA_SINTETICOS,
            salida_dir="modelos/test",
            prueba_rapida=True,
        )
