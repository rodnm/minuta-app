"""Módulo de parches de compatibilidad del entorno para Minuta (minuta/compat.py).

Garantiza la correcta ejecución de faster-whisper en Windows evitando incompatibilidades
de descompresión en httpx2 y parámetros no soportados en ciertas versiones de PyAV.

ESTRICTAMENTE PROHIBIDO importar nada desde evaluacion/.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PARCHES_APLICADOS: bool = False


def _parchear_httpx2(forzar: bool = False) -> None:
    """Aplica envoltorio a BrotliDecoder en httpx2 para descartar kwargs incompatibles."""
    try:
        import httpx2._decoders as dec

        if hasattr(dec.BrotliDecoder, "_minuta_parchado") and not forzar:
            return

        orig_init = dec.BrotliDecoder.__init__

        def safe_init(self: Any, *args: Any, **kwargs: Any) -> None:
            orig_init(self, *args, **kwargs)
            proc_original = self._decompress

            def safe_proc(data: bytes, **kw: Any) -> bytes:
                try:
                    return proc_original(data, **kw)
                except TypeError:
                    return proc_original(data)

            self._decompress = safe_proc

        dec.BrotliDecoder.__init__ = safe_init
        dec.BrotliDecoder._minuta_parchado = True  # type: ignore[attr-defined]
    except (ImportError, AttributeError) as exc:
        logger.debug("No se pudo aplicar parche a httpx2: %s", exc)


def _parchear_av(forzar: bool = False) -> None:
    """Aplica envoltorio defensivo a av.open tolerando metadata_errors='ignore'."""
    try:
        import av

        if getattr(av.open, "_minuta_parchado", False) and not forzar:
            return

        orig_av_open = av.open

        def safe_av_open(*args: Any, **kwargs: Any) -> Any:
            try:
                return orig_av_open(*args, **kwargs)
            except TypeError as err:
                if "metadata_errors" in str(err):
                    kwargs.pop("metadata_errors", None)
                    return orig_av_open(*args, **kwargs)
                raise

        safe_av_open._minuta_parchado = True  # type: ignore[attr-defined]
        av.open = safe_av_open
    except (ImportError, AttributeError) as exc:
        logger.debug("No se pudo aplicar parche a av: %s", exc)


def aplicar_parches_compatibilidad() -> None:
    """Asegura la compatibilidad del entorno para PyAV y httpx2.

    Es seguro invocar esta función múltiples veces (idempotente).
    """
    global _PARCHES_APLICADOS
    if _PARCHES_APLICADOS:
        return

    _parchear_httpx2()
    _parchear_av()
    _PARCHES_APLICADOS = True


def obtener_directorio_whisper_cache(crear_si_no_existe: bool = True) -> str:
    """Retorna la ruta absoluta del directorio de caché de modelos Whisper.

    Respeta la variable de entorno WHISPER_CACHE si está configurada.
    Por defecto utiliza %LOCALAPPDATA%\\minuta-cache\\whisper (en Windows)
    o ~/.cache/minuta/whisper (en Linux/macOS).
    """
    cache = os.environ.get("WHISPER_CACHE")
    if cache:
        ruta = Path(cache)
    else:
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            ruta = Path(localappdata) / "minuta-cache" / "whisper"
        else:
            ruta = Path.home() / ".cache" / "minuta" / "whisper"

    if crear_si_no_existe:
        try:
            ruta.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("No se pudo crear el directorio de caché %s: %s", ruta, e)

    return str(ruta)
