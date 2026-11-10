"""Módulo de evaluación de velocidad y consumo de memoria (evaluacion/velocidad.py).

Evalúa la hipótesis pre-registrada H2 de Minuta:
"small int8 + VAD procesa 1 h en la laptop.
Confirmada si: RTF <= 0.33 (<= 20 min por hora de audio).
Falsada si: RTF > 0.50 (> 30 min por hora de audio).
Zona intermedia: 20 min < tiempo <= 30 min (0.33 < RTF <= 0.50)."
"""

from __future__ import annotations

import argparse
from enum import Enum
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
from typing import Any, Sequence
import wave

import psutil


class VeredictoH2(str, Enum):
    """Veredicto formal de la hipótesis H2 bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    INTERMEDIA = "INTERMEDIA"


def _aplicar_parches_compatibilidad() -> None:
    """Asegura compatibilidad de descompresión Brotli y PyAV en el entorno de ejecución."""
    # Parche 1: BrotliDecoder en httpx2 para evitar TypeError con output_buffer_limit
    try:
        import httpx2._decoders as dec

        orig_init = dec.BrotliDecoder.__init__

        def safe_init(self: Any) -> None:
            orig_init(self)
            proc_original = self._decompress

            def safe_proc(data: bytes, **kwargs: Any) -> bytes:
                try:
                    return proc_original(data, **kwargs)
                except TypeError:
                    return proc_original(data)

            self._decompress = safe_proc

        dec.BrotliDecoder.__init__ = safe_init
    except Exception:
        pass

    # Parche 2: av.open en PyAV para tolerar metadata_errors si la versión instalada no lo soporta
    try:
        import av

        orig_av_open = av.open

        def safe_av_open(*args: Any, **kwargs: Any) -> Any:
            try:
                return orig_av_open(*args, **kwargs)
            except TypeError as err:
                if "metadata_errors" in str(err):
                    kwargs.pop("metadata_errors", None)
                    return orig_av_open(*args, **kwargs)
                raise

        av.open = safe_av_open
    except Exception:
        pass


def obtener_directorio_cache(crear_si_no_existe: bool = True) -> str:
    """Retorna la ruta absoluta del directorio de caché para modelos Whisper.

    Respeta la variable de entorno WHISPER_CACHE si está definida;
    en caso contrario utiliza %LOCALAPPDATA%\\minuta-cache\\whisper (en Windows)
    o ~/.cache/minuta/whisper en otros sistemas operativos.
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
        except OSError:
            pass

    return str(ruta.resolve())


def obtener_ram_rss_mb() -> float:
    """Retorna la memoria residente (RSS) del proceso actual en megabytes."""
    proceso = psutil.Process(os.getpid())
    return proceso.memory_info().rss / (1024.0 * 1024.0)


def calcular_rtf(tiempo_transcripcion: float, duracion_audio: float) -> tuple[float, float]:
    """Calcula el Real-Time Factor (RTF) y proyecta los minutos requeridos por hora de audio.

    RTF = tiempo_transcripcion / duracion_audio.
    minutos_por_hora = RTF * 60.
    """
    if duracion_audio <= 0:
        return 0.0, 0.0
    rtf = tiempo_transcripcion / duracion_audio
    minutos_por_hora = rtf * 60.0
    return rtf, minutos_por_hora


def evaluar_hipotesis_h2(rtf: float) -> dict[str, Any]:
    """Aplica la regla de decisión pre-registrada de la hipótesis H2.

    Confirmada si: RTF <= 0.33 (<= 20 min por hora de audio).
    Falsada si: RTF > 0.50 (> 30 min por hora de audio).
    Zona intermedia: 0.33 < RTF <= 0.50 (20 min < tiempo <= 30 min).
    """
    minutos_por_hora = rtf * 60.0

    if rtf <= 0.33:
        veredicto = VeredictoH2.CONFIRMADA
        motivo = (
            f"Confirmada: RTF ({rtf:.4f}) <= 0.33 "
            f"({minutos_por_hora:.2f} min por hora de audio <= 20 min)."
        )
    elif rtf > 0.50:
        veredicto = VeredictoH2.FALSADA
        motivo = (
            f"Falsada: RTF ({rtf:.4f}) > 0.50 "
            f"({minutos_por_hora:.2f} min por hora de audio > 30 min)."
        )
    else:
        veredicto = VeredictoH2.INTERMEDIA
        motivo = (
            f"Zona intermedia: RTF ({rtf:.4f}) entre 0.33 y 0.50 "
            f"({minutos_por_hora:.2f} min por hora de audio entre 20 y 30 min)."
        )

    return {
        "rtf": rtf,
        "minutos_por_hora": minutos_por_hora,
        "veredicto": veredicto,
        "motivo": motivo,
    }


def generar_audio_sintetico(
    duracion_segundos: float = 30.0,
    ruta_destino: str | Path | None = None,
) -> Path:
    """Genera un archivo .wav temporal con modulación senoidal en memoria/disco.

    Formato: 16 kHz, mono, 16-bit PCM (nativo para Whisper).
    Cumple la regla de no versionar ni publicar audios en el repositorio.
    """
    if ruta_destino is None:
        directorio_temp = Path(tempfile.gettempdir())
        ruta_archivo = directorio_temp / f"minuta_audio_sintetico_{int(time.time() * 1000)}.wav"
    else:
        ruta_archivo = Path(ruta_destino)

    tasa_muestreo = 16000
    frecuencia = 440.0
    num_muestras = int(tasa_muestreo * duracion_segundos)

    with wave.open(str(ruta_archivo), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(tasa_muestreo)

        valores_muestra = bytearray()
        for i in range(num_muestras):
            t = i / tasa_muestreo
            # Modulación para simular estructura espectral básica
            muestra_float = 0.5 * math.sin(2.0 * math.pi * frecuencia * t)
            # Agregar componente armónica secundaria
            muestra_float += 0.25 * math.sin(2.0 * math.pi * (frecuencia * 1.5) * t)
            muestra_int = int(muestra_float * 32767.0)
            # Acotar a 16 bits firmado
            muestra_int = max(-32768, min(32767, muestra_int))
            valores_muestra.extend(struct.pack("<h", muestra_int))

        wf.writeframes(valores_muestra)

    return ruta_archivo


def obtener_duracion_audio(ruta_audio: str | Path) -> float:
    """Obtiene la duración en segundos de un archivo .wav o devuelve 0.0 si falla."""
    try:
        with wave.open(str(ruta_audio), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames) / float(rate)
    except Exception:
        pass
    return 0.0


def ejecutar_evaluacion_velocidad(
    audio_path: str | Path | None = None,
    modelos: Sequence[str] | None = None,
    duracion_segundos: float = 30.0,
    compute_type: str = "int8",
    device: str = "cpu",
    vad: bool = True,
    simulado: bool = False,
) -> dict[str, Any]:
    """Ejecuta la medición de RTF y memoria RSS para los modelos especificados.

    Permite ejecución real mediante faster-whisper o modo `--simulado` determinista.
    """
    lista_modelos = list(modelos) if modelos else ["base", "small", "large-v3-turbo"]
    es_audio_temporal = False
    ruta_audio_efectiva: Path

    if audio_path is not None:
        ruta_audio_efectiva = Path(audio_path).resolve()
        if not ruta_audio_efectiva.exists():
            raise FileNotFoundError(f"No se encontró el audio especificado en: {ruta_audio_efectiva}")
        duracion_audio = obtener_duracion_audio(ruta_audio_efectiva)
        if duracion_audio <= 0:
            duracion_audio = duracion_segundos
    else:
        ruta_audio_efectiva = generar_audio_sintetico(duracion_segundos=duracion_segundos)
        es_audio_temporal = True
        duracion_audio = duracion_segundos

    try:
        resultados_modelos: dict[str, dict[str, Any]] = {}

        for modelo in lista_modelos:
            modelo_limpio = modelo.strip()
            if not modelo_limpio:
                continue

            if simulado:
                # Simulación determinista calibrada según orden de magnitud de Whisper
                if "base" in modelo_limpio:
                    t_carga = 0.35
                    rtf_sim = 0.08
                    ram_mb = 380.0
                elif "small" in modelo_limpio:
                    t_carga = 0.85
                    rtf_sim = 0.22
                    ram_mb = 680.0
                else:  # large o turbo
                    t_carga = 1.90
                    rtf_sim = 0.42
                    ram_mb = 1250.0

                t_transcripcion = rtf_sim * duracion_audio
                rtf, min_h = calcular_rtf(t_transcripcion, duracion_audio)
                eval_h2 = evaluar_hipotesis_h2(rtf)

                resultados_modelos[modelo_limpio] = {
                    "tiempo_carga_s": round(t_carga, 3),
                    "tiempo_transcripcion_s": round(t_transcripcion, 3),
                    "rtf": round(rtf, 4),
                    "minutos_por_hora": round(min_h, 2),
                    "ram_rss_mb": round(ram_mb, 1),
                    "veredicto_h2": eval_h2["veredicto"].value,
                    "motivo": eval_h2["motivo"],
                }
            else:
                # Carga real de faster-whisper
                _aplicar_parches_compatibilidad()
                os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
                from faster_whisper import WhisperModel

                dir_cache = obtener_directorio_cache()
                t0_carga = time.perf_counter()
                modelo_whisper = WhisperModel(
                    model_size_or_path=modelo_limpio,
                    device=device,
                    compute_type=compute_type,
                    download_root=dir_cache,
                )
                tiempo_carga_s = time.perf_counter() - t0_carga

                t0_trans = time.perf_counter()
                segmentos, info = modelo_whisper.transcribe(
                    str(ruta_audio_efectiva),
                    language="es",
                    vad_filter=vad,
                    temperature=0.0,
                )
                # Iterar completamente el generador para procesar todo el audio
                _ = [s.text for s in segmentos]
                tiempo_transcripcion_s = time.perf_counter() - t0_trans

                duracion_efectiva = (
                    info.duration
                    if hasattr(info, "duration") and info.duration and info.duration > 0
                    else duracion_audio
                )
                rtf, min_h = calcular_rtf(tiempo_transcripcion_s, duracion_efectiva)
                ram_rss = obtener_ram_rss_mb()
                eval_h2 = evaluar_hipotesis_h2(rtf)

                resultados_modelos[modelo_limpio] = {
                    "tiempo_carga_s": round(tiempo_carga_s, 3),
                    "tiempo_transcripcion_s": round(tiempo_transcripcion_s, 3),
                    "rtf": round(rtf, 4),
                    "minutos_por_hora": round(min_h, 2),
                    "ram_rss_mb": round(ram_rss, 1),
                    "veredicto_h2": eval_h2["veredicto"].value,
                    "motivo": eval_h2["motivo"],
                }

        # Veredicto general pre-registrado en H2 (basado en 'small')
        if "small" in resultados_modelos:
            veredicto_general = resultados_modelos["small"]["veredicto_h2"]
        elif resultados_modelos:
            primer_modelo = next(iter(resultados_modelos))
            veredicto_general = resultados_modelos[primer_modelo]["veredicto_h2"]
        else:
            veredicto_general = VeredictoH2.INTERMEDIA.value

        return {
            "audio": str(ruta_audio_efectiva) if not es_audio_temporal else "<sintetico_temporal>",
            "duracion_audio_s": round(duracion_audio, 2),
            "device": device,
            "compute_type": compute_type,
            "vad": vad,
            "simulado": simulado,
            "modelos": resultados_modelos,
            "veredicto_general_h2": veredicto_general,
        }

    finally:
        if es_audio_temporal and ruta_audio_efectiva.exists():
            try:
                ruta_audio_efectiva.unlink()
            except OSError:
                pass


def formatear_tabla_resultados(datos: dict[str, Any]) -> str:
    """Genera la representación tabular formateada de los resultados para la terminal."""
    lineas: list[str] = []

    if datos.get("simulado"):
        lineas.append("\n" + "=" * 78)
        lineas.append("  [ADVERTENCIA] SIMULADO: no es una medición real con descarga de modelos.")
        lineas.append("=" * 78)

    lineas.append(
        f"\nAudio evaluado: {datos.get('audio')} | "
        f"Duración: {datos.get('duracion_audio_s')}s | "
        f"Device: {datos.get('device')} | "
        f"Compute: {datos.get('compute_type')} | "
        f"VAD: {datos.get('vad')}\n"
    )

    encabezado = (
        f"{'Modelo':<18} | {'Carga (s)':<10} | {'Trans (s)':<10} | "
        f"{'RTF':<8} | {'Min/h':<8} | {'RAM (MB)':<10} | {'Veredicto H2':<12}"
    )
    separador = "-" * len(encabezado)

    lineas.append(encabezado)
    lineas.append(separador)

    modelos = datos.get("modelos", {})
    for nombre, metricas in modelos.items():
        linea = (
            f"{nombre:<18} | "
            f"{metricas['tiempo_carga_s']:<10.2f} | "
            f"{metricas['tiempo_transcripcion_s']:<10.2f} | "
            f"{metricas['rtf']:<8.4f} | "
            f"{metricas['minutos_por_hora']:<8.1f} | "
            f"{metricas['ram_rss_mb']:<10.1f} | "
            f"{metricas['veredicto_h2']:<12}"
        )
        lineas.append(linea)

    lineas.append(separador)
    lineas.append(f"Veredicto General H2 (según 'small'): {datos.get('veredicto_general_h2')}\n")

    return "\n".join(lineas)


def parsear_argumentos(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Configura y analiza los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Medición de velocidad y memoria de Whisper (H2: RTF <= 0.33 para 'small')."
    )
    parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Ruta a un archivo de audio (.wav, .mp3, etc.). Si se omite, genera audio temporal.",
    )
    parser.add_argument(
        "--modelos",
        type=str,
        default="base,small,large-v3-turbo",
        help="Lista de modelos separados por coma (default: base,small,large-v3-turbo).",
    )
    parser.add_argument(
        "--duracion",
        type=float,
        default=30.0,
        help="Duración en segundos del audio sintético a generar si --audio no se provee (default: 30.0).",
    )
    parser.add_argument(
        "--compute-type",
        type=str,
        default="int8",
        help="Tipo de cuantización de faster-whisper (default: int8).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Dispositivo de cómputo para faster-whisper (default: cpu).",
    )
    parser.add_argument(
        "--vad",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Habilitar o deshabilitar VAD filter (default: True, --no-vad para deshabilitar).",
    )
    parser.add_argument(
        "--simulado",
        action="store_true",
        default=False,
        help="Ejecución simulada sin descargar modelos reales (ideal para CI y pruebas rápidas).",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default=None,
        help="Ruta opcional para guardar el informe de resultados en formato JSON.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada principal para CLI de evaluacion.velocidad."""
    args = parsear_argumentos(argv)
    modelos_lista = [m.strip() for m in args.modelos.split(",") if m.strip()]

    resultados = ejecutar_evaluacion_velocidad(
        audio_path=args.audio,
        modelos=modelos_lista,
        duracion_segundos=args.duracion,
        compute_type=args.compute_type,
        device=args.device,
        vad=args.vad,
        simulado=args.simulado,
    )

    tabla = formatear_tabla_resultados(resultados)
    print(tabla)

    if args.salida:
        p_salida = Path(args.salida).resolve()
        p_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(p_salida, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        print(f"Resultados guardados en: {p_salida}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
