"""Pruebas unitarias para el arnés de velocidad y consumo de recursos (evaluacion/velocidad.py).

Verifica la medición de RTF y RAM de faster-whisper bajo la hipótesis pre-registrada H2:
- Confirmada si: RTF <= 0.33 (<= 20 min por hora de audio).
- Falsada si: RTF > 0.50 (> 30 min por hora de audio).
- Zona intermedia: 20 min < tiempo <= 30 min (0.33 < RTF <= 0.50).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import wave
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluacion.velocidad import (
    VeredictoH2,
    calcular_rtf,
    evaluar_hipotesis_h2,
    generar_audio_sintetico,
    obtener_directorio_cache,
    obtener_ram_rss_mb,
    parsear_argumentos,
    formatear_tabla_resultados,
    ejecutar_evaluacion_velocidad,
    main as velocidad_main,
)


def test_calcular_rtf_y_minutos_por_hora() -> None:
    """Verifica el cálculo aritmético de RTF y proyección de minutos por hora."""
    # 10 segundos de transcripción para 30 segundos de audio: RTF = 1/3 = ~0.3333
    rtf, min_h = calcular_rtf(tiempo_transcripcion=10.0, duracion_audio=30.0)
    assert pytest.approx(rtf, rel=1e-3) == 0.3333
    assert pytest.approx(min_h, rel=1e-3) == 20.0

    # 5 segundos para 50 segundos de audio: RTF = 0.1, min/h = 6.0
    rtf2, min_h2 = calcular_rtf(5.0, 50.0)
    assert pytest.approx(rtf2, rel=1e-3) == 0.1
    assert pytest.approx(min_h2, rel=1e-3) == 6.0

    # Protección contra división por cero
    rtf_cero, min_h_cero = calcular_rtf(10.0, 0.0)
    assert rtf_cero == 0.0
    assert min_h_cero == 0.0


def test_evaluar_hipotesis_h2_confirmada() -> None:
    """Verifica umbrales de confirmación: RTF <= 0.33 (<= 20 min/h)."""
    res1 = evaluar_hipotesis_h2(0.20)
    assert res1["veredicto"] == VeredictoH2.CONFIRMADA
    assert res1["minutos_por_hora"] == pytest.approx(12.0)
    assert "Confirmada" in res1["motivo"]

    res2 = evaluar_hipotesis_h2(0.33)
    assert res2["veredicto"] == VeredictoH2.CONFIRMADA
    assert res2["minutos_por_hora"] == pytest.approx(19.8)


def test_evaluar_hipotesis_h2_intermedia() -> None:
    """Verifica zona intermedia: 0.33 < RTF <= 0.50 (20 min < tiempo <= 30 min)."""
    res = evaluar_hipotesis_h2(0.40)
    assert res["veredicto"] == VeredictoH2.INTERMEDIA
    assert res["minutos_por_hora"] == pytest.approx(24.0)
    assert "intermedia" in res["motivo"].lower()

    res_borde = evaluar_hipotesis_h2(0.50)
    assert res_borde["veredicto"] == VeredictoH2.INTERMEDIA
    assert res_borde["minutos_por_hora"] == pytest.approx(30.0)


def test_evaluar_hipotesis_h2_falsada() -> None:
    """Verifica umbral de falsación: RTF > 0.50 (> 30 min/h)."""
    res1 = evaluar_hipotesis_h2(0.51)
    assert res1["veredicto"] == VeredictoH2.FALSADA
    assert res1["minutos_por_hora"] == pytest.approx(30.6)
    assert "Falsada" in res1["motivo"]

    res2 = evaluar_hipotesis_h2(1.2)
    assert res2["veredicto"] == VeredictoH2.FALSADA
    assert res2["minutos_por_hora"] == pytest.approx(72.0)


def test_generar_audio_sintetico_temporal() -> None:
    """Valida la generación de archivo .wav temporal válido y su contenido PCM."""
    duracion_solicitada = 1.5
    ruta_wav = generar_audio_sintetico(duracion_segundos=duracion_solicitada)
    try:
        assert ruta_wav.exists()
        assert ruta_wav.is_file()

        with wave.open(str(ruta_wav), "rb") as wf:
            canales = wf.getnchannels()
            ancho_muestra = wf.getsampwidth()
            tasa_muestreo = wf.getframerate()
            num_frames = wf.getnframes()

            assert canales == 1, "Debe ser canal mono"
            assert ancho_muestra == 2, "Debe ser muestra de 16 bits (2 bytes)"
            assert tasa_muestreo == 16000, "Debe ser frecuencia de 16000 Hz nativa de Whisper"
            duracion_real = num_frames / tasa_muestreo
            assert pytest.approx(duracion_real, abs=0.05) == duracion_solicitada
    finally:
        if ruta_wav.exists():
            ruta_wav.unlink()

    assert not ruta_wav.exists(), "El archivo temporal debe poder ser eliminado"


def test_obtener_directorio_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que el directorio de caché respete WHISPER_CACHE y LOCALAPPDATA."""
    # Caso variable explícita WHISPER_CACHE
    monkeypatch.setenv("WHISPER_CACHE", r"C:\custom_cache\whisper")
    assert obtener_directorio_cache() == r"C:\custom_cache\whisper"

    # Caso fallback con LOCALAPPDATA
    monkeypatch.delenv("WHISPER_CACHE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Test\AppData\Local")
    ruta_esperada = str(Path(r"C:\Users\Test\AppData\Local\minuta-cache\whisper"))
    assert str(Path(obtener_directorio_cache())) == ruta_esperada


def test_obtener_ram_rss_mb() -> None:
    """Verifica que la lectura de memoria RSS devuelva un valor positivo razonable."""
    ram_mb = obtener_ram_rss_mb()
    assert isinstance(ram_mb, float)
    assert ram_mb > 5.0, "El proceso actual debe consumir al menos 5 MB de RAM"


def test_parsear_argumentos_defaults() -> None:
    """Verifica valores por defecto del analizador de argumentos CLI."""
    args = parsear_argumentos([])
    assert args.audio is None
    assert args.modelos == "base,small,large-v3-turbo"
    assert args.duracion == 30.0
    assert args.compute_type == "int8"
    assert args.device == "cpu"
    assert args.vad is True
    assert args.simulado is False
    assert args.salida is None


def test_parsear_argumentos_personalizados() -> None:
    """Verifica el parseo de argumentos CLI personalizados."""
    cli_args = [
        "--audio", "clip_prueba.wav",
        "--modelos", "base,small",
        "--duracion", "15.5",
        "--compute-type", "float16",
        "--device", "cuda",
        "--no-vad",
        "--simulado",
        "--salida", "resultados.json",
    ]
    args = parsear_argumentos(cli_args)
    assert args.audio == "clip_prueba.wav"
    assert args.modelos == "base,small"
    assert args.duracion == 15.5
    assert args.compute_type == "float16"
    assert args.device == "cuda"
    assert args.vad is False
    assert args.simulado is True
    assert args.salida == "resultados.json"


def test_ejecutar_evaluacion_simulada_completa() -> None:
    """Verifica la ejecución completa del experimento en modo simulado."""
    resultado = ejecutar_evaluacion_velocidad(
        modelos=["base", "small"],
        duracion_segundos=10.0,
        simulado=True,
    )

    assert resultado["simulado"] is True
    assert resultado["duracion_audio_s"] == 10.0
    assert "base" in resultado["modelos"]
    assert "small" in resultado["modelos"]

    small_res = resultado["modelos"]["small"]
    assert small_res["rtf"] > 0
    assert small_res["tiempo_transcripcion_s"] > 0
    assert small_res["ram_rss_mb"] > 0
    assert small_res["veredicto_h2"] in [v.value for v in VeredictoH2]

    # Veredicto general basado en small
    assert resultado["veredicto_general_h2"] == small_res["veredicto_h2"]


def test_formatear_tabla_resultados_contiene_advertencia_simulada() -> None:
    """Verifica que la tabla formateada incluya aviso en modo simulado."""
    resultado = ejecutar_evaluacion_velocidad(
        modelos=["base", "small"],
        duracion_segundos=5.0,
        simulado=True,
    )
    tabla = formatear_tabla_resultados(resultado)
    assert "SIMULADO: no es una medición" in tabla
    assert "base" in tabla
    assert "small" in tabla
    assert "RTF" in tabla
    assert "Veredicto" in tabla


def test_main_cli_simulado_guarda_json(tmp_path: Path) -> None:
    """Verifica la ejecución de main CLI con guardado de archivo JSON."""
    ruta_salida = tmp_path / "salida_velocidad.json"
    codigo_salida = velocidad_main([
        "--simulado",
        "--modelos", "base,small",
        "--duracion", "5.0",
        "--salida", str(ruta_salida),
    ])

    assert codigo_salida == 0
    assert ruta_salida.exists()

    with open(ruta_salida, encoding="utf-8") as f:
        datos = json.load(f)

    assert datos["simulado"] is True
    assert "modelos" in datos
    assert "small" in datos["modelos"]
    assert datos["veredicto_general_h2"] == datos["modelos"]["small"]["veredicto_h2"]
