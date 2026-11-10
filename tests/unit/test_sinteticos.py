"""Pruebas unitarias para el generador de datos sintéticos (T03, S4, S15, H4, H5).

Valida los modelos Pydantic de datos sintéticos, las proporciones requeridas de clases,
el modo determinista dry-run, el CLI y la muestra sintética representativa.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from entrenamiento.generar_sinteticos import (
    CLASES_VALIDAS,
    ConversacionSintetica,
    DatasetSintetico,
    EtiquetaClase,
    SegmentoSintetico,
    calcular_estadisticas_dataset,
    generar_conversacion_sintetica_dry_run,
    generar_dataset_sintetico,
    validar_distribucion_reuniones,
)


def test_clases_validas_definidas():
    esperadas = {"idea", "tarea", "acuerdo", "pregunta", "relleno"}
    assert set(CLASES_VALIDAS) == esperadas


def test_segmento_sintetico_valido():
    seg = SegmentoSintetico(
        id=1,
        inicio_s=0.0,
        fin_s=5.0,
        texto="Buenos días, iniciamos la sesión para coordinar el paper.",
        etiqueta="relleno",
        orador="Moderador",
    )
    assert seg.id == 1
    assert seg.etiqueta == "relleno"
    assert seg.inicio_s == 0.0
    assert seg.fin_s == 5.0


def test_segmento_sintetico_etiqueta_invalida():
    with pytest.raises(ValidationError):
        SegmentoSintetico(
            id=1,
            inicio_s=0.0,
            fin_s=5.0,
            texto="Texto cualquiera.",
            etiqueta="categoria_inexistente",  # type: ignore
        )


def test_segmento_sintetico_intervalo_invalido():
    with pytest.raises(ValidationError):
        SegmentoSintetico(
            id=2,
            inicio_s=10.0,
            fin_s=4.0,
            texto="Texto con tiempos inconsistentes.",
            etiqueta="idea",
        )


def test_generar_conversacion_dry_run_ponencia():
    conv = generar_conversacion_sintetica_dry_run(
        tipo="ponencia",
        indice=1,
        num_segmentos=60,
        seed=101,
    )
    assert isinstance(conv, ConversacionSintetica)
    assert conv.tipo == "ponencia"
    assert len(conv.segmentos) == 60
    assert conv.duracion_s > 0

    # Comprobar monotonicidad de marcas temporales
    for s in conv.segmentos:
        assert s.inicio_s <= s.fin_s


def test_generar_conversacion_dry_run_reunion_proporciones():
    # En reuniones se exige: tarea >= 6% y relleno >= 10%
    conv = generar_conversacion_sintetica_dry_run(
        tipo="reunion",
        indice=1,
        num_segmentos=80,
        seed=202,
    )
    assert conv.tipo == "reunion"
    assert len(conv.segmentos) == 80

    conteo = {c: 0 for c in CLASES_VALIDAS}
    for s in conv.segmentos:
        conteo[s.etiqueta] += 1

    total = len(conv.segmentos)
    pct_tarea = conteo["tarea"] / total
    pct_relleno = conteo["relleno"] / total

    assert pct_tarea >= 0.06, f"Porcentaje de tarea {pct_tarea:.2%} < 6%"
    assert pct_relleno >= 0.10, f"Porcentaje de relleno {pct_relleno:.2%} < 10%"


def test_dataset_completo_dry_run_proporciones_y_cinco_clases():
    dataset = generar_dataset_sintetico(
        n_por_tipo=2,
        tipos=["ponencia", "reunion", "entrevista"],
        dry_run=True,
        seed=42,
    )
    assert isinstance(dataset, DatasetSintetico)
    assert len(dataset.conversaciones) == 6

    stats = calcular_estadisticas_dataset(dataset)
    for c in CLASES_VALIDAS:
        assert stats["conteo_por_clase"].get(c, 0) > 0, f"La clase {c} no aparece en el dataset"

    # Validar reuniones dentro del dataset
    cumple_reuniones, detalle = validar_distribucion_reuniones(dataset)
    assert cumple_reuniones, f"Falla distribución de reuniones: {detalle}"


def test_reproducibilidad_con_semilla_fija():
    ds1 = generar_dataset_sintetico(n_por_tipo=1, tipos=["reunion"], dry_run=True, seed=999)
    ds2 = generar_dataset_sintetico(n_por_tipo=1, tipos=["reunion"], dry_run=True, seed=999)

    assert ds1.model_dump() == ds2.model_dump()


def test_cli_dry_run_ejecucion():
    cmd = [
        sys.executable,
        "-m",
        "entrenamiento.generar_sinteticos",
        "--n",
        "2",
        "--dry-run",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    assert res.returncode == 0, f"Error en CLI: {res.stderr}"
    salida = res.stdout
    assert "Conteo por clase:" in salida
    for c in CLASES_VALIDAS:
        assert c in salida


def test_archivo_muestra_sinteticos_cumple_contrato():
    ruta_muestra = ROOT_DIR / "entrenamiento" / "datos" / "sinteticos_muestra.json"
    assert ruta_muestra.exists(), "El archivo de muestra no fue creado aún"

    with open(ruta_muestra, "r", encoding="utf-8") as f:
        data = json.load(f)

    dataset = DatasetSintetico.model_validate(data)
    assert len(dataset.conversaciones) > 0
    cumple_reuniones, detalle = validar_distribucion_reuniones(dataset)
    assert cumple_reuniones, f"La muestra no cumple la distribución de reuniones: {detalle}"
