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
    FuenteConversacion,
    SegmentoSintetico,
    calcular_estadisticas_dataset,
    generar_conversacion_gemini,
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


def test_conversacion_sintetica_campo_fuente():
    conv_plantilla = ConversacionSintetica(
        id="c1",
        tipo="ponencia",
        titulo="Ponencia",
        duracion_s=10.0,
        fuente="plantilla",
        segmentos=[],
    )
    assert conv_plantilla.fuente == "plantilla"

    conv_gemini = ConversacionSintetica(
        id="c2",
        tipo="reunion",
        titulo="Reunión",
        duracion_s=20.0,
        fuente="gemini",
        segmentos=[],
    )
    assert conv_gemini.fuente == "gemini"

    with pytest.raises(ValidationError):
        ConversacionSintetica(
            id="c3",
            tipo="entrevista",
            titulo="Entrevista",
            duracion_s=30.0,
            fuente="fuente_invalida",  # type: ignore
            segmentos=[],
        )


def test_calcular_estadisticas_incluye_unicos_y_desglose_fuentes():
    seg1 = SegmentoSintetico(id=1, inicio_s=0.0, fin_s=4.0, texto="Texto A", etiqueta="idea")
    seg2 = SegmentoSintetico(id=2, inicio_s=4.5, fin_s=8.0, texto="Texto B", etiqueta="tarea")
    seg3 = SegmentoSintetico(id=3, inicio_s=8.5, fin_s=12.0, texto="Texto A", etiqueta="idea")

    c1 = ConversacionSintetica(
        id="c1", tipo="ponencia", titulo="P1", duracion_s=15.0, fuente="gemini", segmentos=[seg1, seg2]
    )
    c2 = ConversacionSintetica(
        id="c2", tipo="reunion", titulo="R1", duracion_s=15.0, fuente="plantilla", segmentos=[seg3]
    )

    ds = DatasetSintetico(
        total_conversaciones=2,
        total_segmentos=3,
        conteo_por_clase={"idea": 2, "tarea": 1, "acuerdo": 0, "pregunta": 0, "relleno": 0},
        proporciones_por_clase={"idea": 0.6667, "tarea": 0.3333},
        porcentaje_unicos=66.67,
        desglose_por_fuente={"gemini": 1, "plantilla": 1},
        conversaciones=[c1, c2],
    )

    stats = calcular_estadisticas_dataset(ds)
    # 2 textos únicos de 3 totales = 2/3 * 100 = 66.67%
    assert stats["porcentaje_unicos"] == pytest.approx(66.67, 0.01)
    assert stats["desglose_por_fuente"]["gemini"] == 1
    assert stats["desglose_por_fuente"]["plantilla"] == 1


def test_modo_estricto_falla_ante_error_api():
    """En modo estricto, si la API falla debe lanzar RuntimeError y no caer a plantilla."""
    with pytest.raises(RuntimeError):
        generar_conversacion_gemini(
            tipo="ponencia",
            indice=1,
            num_segmentos=10,
            estricto=True,
            api_key="dummy_test_key_invalida",
        )


def test_modo_no_estricto_permite_fallback_a_plantilla():
    """En modo no estricto, ante error cae a plantilla con fuente='plantilla'."""
    conv = generar_conversacion_gemini(
        tipo="ponencia",
        indice=1,
        num_segmentos=10,
        estricto=False,
        api_key="dummy_test_key_invalida",
    )
    assert isinstance(conv, ConversacionSintetica)
    assert conv.fuente == "plantilla"
    assert len(conv.segmentos) == 10


def test_cli_argumentos_estricto_y_reporte_unicos():
    cmd = [
        sys.executable,
        "-m",
        "entrenamiento.generar_sinteticos",
        "--n",
        "1",
        "--dry-run",
        "--estricto",
        "--modelo",
        "gemini-3.8-flash",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    assert res.returncode == 0
    assert "Porcentaje de segmentos únicos:" in res.stdout
    assert "Desglose por fuente:" in res.stdout

