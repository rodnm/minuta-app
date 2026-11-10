"""Pruebas unitarias para minuta/transcribir.py.

Verifica la orquestación de la transcripción con faster-whisper (mockeado),
la construcción del objeto Pydantic Transcripcion y la interfaz de línea de comandos (CLI).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from minuta.esquemas import Segmento, Transcripcion
from minuta.transcribir import main, transcribir_audio


def _crear_segmento_mock(id_seg: int, start: float, end: float, text: str):
    """Crea un objeto mock similar a Segment de faster-whisper."""
    return SimpleNamespace(
        id=id_seg,
        seek=0,
        start=start,
        end=end,
        text=text,
        tokens=[10, 20],
        temperature=0.0,
        avg_logprob=-0.2,
        compression_ratio=1.1,
        no_speech_prob=0.01,
        words=None,
    )


@patch("minuta.transcribir.WhisperModel")
def test_transcribir_audio_con_mock(mock_whisper_class, tmp_path):
    """Verifica que transcribir_audio inicializa WhisperModel e invoca transcribe con los hiperparámetros de Minuta."""
    mock_instance = MagicMock()
    mock_whisper_class.return_value = mock_instance

    mock_info = SimpleNamespace(duration=12.5, language="es")
    mock_segments = [
        _crear_segmento_mock(1, 0.0, 5.2, " Hola a todos en este workshop. "),
        _crear_segmento_mock(2, 5.5, 12.5, " Presentamos nuestro benchmark y dataset. "),
    ]
    mock_instance.transcribe.return_value = (iter(mock_segments), mock_info)

    audio_fake = tmp_path / "audio_prueba.wav"
    audio_fake.write_bytes(b"RIFFdummydata")

    tx = transcribir_audio(
        audio=audio_fake,
        modelo="small",
        device="cpu",
        compute_type="int8",
        vad_filter=True,
        usar_hotwords=True,
    )

    # Validar que WhisperModel fue instanciado correctamente
    mock_whisper_class.assert_called_once()
    args, kwargs = mock_whisper_class.call_args
    assert kwargs["device"] == "cpu"
    assert kwargs["compute_type"] == "int8"
    assert "download_root" in kwargs
    assert kwargs["download_root"] is not None

    # Validar llamada a transcribe
    mock_instance.transcribe.assert_called_once()
    t_args, t_kwargs = mock_instance.transcribe.call_args
    assert t_kwargs["language"] == "es"
    assert t_kwargs["temperature"] == 0.0
    assert t_kwargs["vad_filter"] is True
    assert "hotwords" in t_kwargs
    assert t_kwargs["hotwords"] is not None
    assert "benchmark" in t_kwargs["hotwords"]

    # Validar objeto Transcripcion resultante
    assert isinstance(tx, Transcripcion)
    assert tx.audio_id == "audio_prueba"
    assert tx.duracion_s == 12.5
    assert tx.modelo == "small"
    assert len(tx.segmentos) == 2

    seg0 = tx.segmentos[0]
    assert isinstance(seg0, Segmento)
    assert seg0.id == 1
    assert seg0.inicio_s == 0.0
    assert seg0.fin_s == 5.2
    assert seg0.texto == "Hola a todos en este workshop."

    seg1 = tx.segmentos[1]
    assert seg1.id == 2
    assert seg1.inicio_s == 5.5
    assert seg1.fin_s == 12.5
    assert seg1.texto == "Presentamos nuestro benchmark y dataset."


@patch("minuta.transcribir.WhisperModel")
def test_transcribir_audio_sin_hotwords(mock_whisper_class, tmp_path):
    """Verifica que si usar_hotwords=False, hotwords no se envía a transcribe."""
    mock_instance = MagicMock()
    mock_whisper_class.return_value = mock_instance

    mock_info = SimpleNamespace(duration=5.0, language="es")
    mock_segments = [_crear_segmento_mock(1, 0.0, 5.0, "Texto simple.")]
    mock_instance.transcribe.return_value = (iter(mock_segments), mock_info)

    audio_fake = tmp_path / "audio_sin_hw.wav"
    audio_fake.write_bytes(b"dummy")

    tx = transcribir_audio(audio_fake, usar_hotwords=False)

    _, t_kwargs = mock_instance.transcribe.call_args
    assert t_kwargs.get("hotwords") is None
    assert len(tx.segmentos) == 1


@patch("minuta.transcribir.WhisperModel")
def test_transcribir_audio_con_glosario_adicional(mock_whisper_class, tmp_path):
    """Verifica que los términos adicionales se incorporen en tx.glosario y en hotwords."""
    mock_instance = MagicMock()
    mock_whisper_class.return_value = mock_instance

    mock_info = SimpleNamespace(duration=4.0, language="es")
    mock_segments = [_crear_segmento_mock(1, 0.0, 4.0, "Probando término.")]
    mock_instance.transcribe.return_value = (iter(mock_segments), mock_info)

    audio_fake = tmp_path / "audio_adicional.wav"
    audio_fake.write_bytes(b"dummy")

    termino_nuevo = "AlgoritmoCuantico"
    tx = transcribir_audio(audio_fake, glosario_adicional=[termino_nuevo])

    assert termino_nuevo in tx.glosario
    _, t_kwargs = mock_instance.transcribe.call_args
    assert termino_nuevo in t_kwargs.get("hotwords", "")


@patch("minuta.transcribir.transcribir_audio")
def test_cli_ejecucion_con_salida_json(mock_transcribir, tmp_path):
    """Verifica la invocación CLI con argumento --salida guardando JSON validado con Pydantic."""
    tx_falsa = Transcripcion(
        audio_id="test_cli",
        duracion_s=10.0,
        modelo="small",
        glosario=["benchmark"],
        segmentos=[Segmento(id=1, inicio_s=0.0, fin_s=10.0, texto="Audio CLI test.")],
    )
    mock_transcribir.return_value = tx_falsa

    audio_input = tmp_path / "audio_cli.m4a"
    audio_input.write_bytes(b"dummy")
    salida_json = tmp_path / "salida_resultado.json"

    codigo_salida = main([
        str(audio_input),
        "--modelo", "small",
        "--salida", str(salida_json),
    ])

    assert codigo_salida == 0
    assert salida_json.exists()

    # Validar que el archivo escrito sea un JSON parseable por Transcripcion
    contenido = salida_json.read_text(encoding="utf-8")
    tx_cargada = Transcripcion.model_validate_json(contenido)
    assert tx_cargada.audio_id == "test_cli"
    assert tx_cargada.duracion_s == 10.0
    assert len(tx_cargada.segmentos) == 1
    assert tx_cargada.segmentos[0].texto == "Audio CLI test."


@patch("minuta.transcribir.transcribir_audio")
def test_cli_con_glosario_cadena_y_archivo(mock_transcribir, tmp_path):
    """Verifica que el argumento --glosario admita archivo de texto o cadena separada por comas."""
    tx_falsa = Transcripcion(
        audio_id="test_glosario",
        duracion_s=5.0,
        modelo="small",
        glosario=["terminoA", "terminoB"],
        segmentos=[],
    )
    mock_transcribir.return_value = tx_falsa

    audio_input = tmp_path / "audio.m4a"
    audio_input.write_bytes(b"dummy")

    # Caso 1: Glosario como archivo de texto (una palabra por línea)
    glosario_file = tmp_path / "glosario.txt"
    glosario_file.write_text("terminoA\nterminoB\n", encoding="utf-8")

    codigo = main([
        str(audio_input),
        "--glosario", str(glosario_file),
    ])
    assert codigo == 0
    call_kwargs = mock_transcribir.call_args[1]
    assert call_kwargs["glosario_adicional"] == ["terminoA", "terminoB"]

    # Caso 2: Glosario como cadena con comas
    codigo = main([
        str(audio_input),
        "--glosario", "palabra1, palabra2",
    ])
    assert codigo == 0
    call_kwargs = mock_transcribir.call_args[1]
    assert call_kwargs["glosario_adicional"] == ["palabra1", "palabra2"]
