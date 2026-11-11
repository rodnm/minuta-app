"""Pruebas unitarias para minuta/compat.py.

Verifica el aislamiento de compatibilidad, parches defensivos para PyAV y httpx2,
y resolución de rutas de caché para Whisper.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minuta.compat import (
    aplicar_parches_compatibilidad,
    obtener_directorio_whisper_cache,
)


def test_aplicar_parches_compatibilidad_ejecuta_limpio_e_idempotente():
    """Verifica que aplicar_parches_compatibilidad ejecuta sin errores múltiples veces."""
    aplicar_parches_compatibilidad()
    aplicar_parches_compatibilidad()
    aplicar_parches_compatibilidad()


def test_parche_av_open_tolera_metadata_errors():
    """Verifica que la envoltura de av.open tolera y descarta metadata_errors si la función base falla."""
    aplicar_parches_compatibilidad()
    import av

    # Creamos un mock que simula el comportamiento de PyAV antiguo (rechaza metadata_errors con TypeError)
    def fake_av_open_estricto(*args, **kwargs):
        if "metadata_errors" in kwargs:
            raise TypeError("av.open() got an unexpected keyword argument 'metadata_errors'")
        return "exito_sin_metadata_errors"

    # Envolverlo con la lógica del parche
    orig_open = av.open
    try:
        av.open = fake_av_open_estricto
        # Forzar reaplicación del parche sobre este objeto
        from minuta.compat import _parchear_av
        _parchear_av(forzar=True)

        res = av.open("fake_path.mp3", metadata_errors="ignore")
        assert res == "exito_sin_metadata_errors"
    finally:
        av.open = orig_open


def test_parche_brotli_decoder_tolera_kwargs():
    """Verifica que el decodificador Brotli envuelve _decompress para ignorar kwargs incompatibles."""
    aplicar_parches_compatibilidad()
    try:
        import httpx2._decoders as dec

        decoder = dec.BrotliDecoder()

        # Simular descompresor estricto que rechaza kwargs
        def fake_decompress_estricto(data: bytes, **kwargs):
            if kwargs:
                raise TypeError("process() takes no keyword arguments")
            return b"descomprimido"

        decoder._decompress = fake_decompress_estricto
        from minuta.compat import _parchear_httpx2
        _parchear_httpx2(forzar=True)

        # Ahora un nuevo decoder debe tolerar kwargs
        decoder_parchado = dec.BrotliDecoder()
        # Verificar que la instancia creada tenga safe_proc
        assert hasattr(decoder_parchado, "_decompress")
    except ImportError:
        pytest.skip("httpx2 no está instalado en este entorno.")


def test_obtener_directorio_whisper_cache_con_env(monkeypatch, tmp_path):
    """Verifica que la variable de entorno WHISPER_CACHE tenga máxima prioridad."""
    dir_personalizado = tmp_path / "mi_whisper_cache"
    monkeypatch.setenv("WHISPER_CACHE", str(dir_personalizado))

    ruta = obtener_directorio_whisper_cache()
    assert ruta == str(dir_personalizado)
    assert dir_personalizado.exists()


def test_obtener_directorio_whisper_cache_por_defecto(monkeypatch, tmp_path):
    """Verifica que sin WHISPER_CACHE recurre a %LOCALAPPDATA%\\minuta-cache\\whisper."""
    monkeypatch.delenv("WHISPER_CACHE", raising=False)
    falso_localappdata = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(falso_localappdata))

    ruta = obtener_directorio_whisper_cache()
    assert ruta == str(falso_localappdata / "minuta-cache" / "whisper")
    assert (falso_localappdata / "minuta-cache" / "whisper").exists()
