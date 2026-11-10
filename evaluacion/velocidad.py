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
import numpy as np


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


def cargar_y_concatenar_audios(
    carpeta: str | Path,
    duracion_objetivo_s: float = 300.0,
) -> np.ndarray:
    """Carga archivos de audio de una carpeta y los concatena en memoria RAM a 16 kHz mono.

    Decodifica cada archivo usando faster_whisper.decode_audio (formato 16 kHz float32 mono).
    Concatena y repite en memoria hasta alcanzar la duración objetivo (por defecto ~300 s / 5 min).
    Cumple estrictamente la regla L21: ningún archivo de audio se escribe fuera de data/privado/.
    Todo el audio concatenado vive únicamente en memoria RAM como numpy array.
    """
    p_carpeta = Path(carpeta).resolve()
    if not p_carpeta.exists() or not p_carpeta.is_dir():
        raise FileNotFoundError(f"El directorio de audios no existe: {p_carpeta}")

    extensiones_validas = {".m4a", ".wav", ".mp3", ".ogg", ".flac", ".aac", ".webm"}
    archivos_audio = sorted(
        [f for f in p_carpeta.iterdir() if f.is_file() and f.suffix.lower() in extensiones_validas],
        key=lambda f: f.name,
    )

    if not archivos_audio:
        raise FileNotFoundError(f"No se encontraron archivos de audio válidos en: {p_carpeta}")

    _aplicar_parches_compatibilidad()
    from faster_whisper import decode_audio

    audios_decodificados: list[np.ndarray] = []
    for f_audio in archivos_audio:
        try:
            arr = decode_audio(str(f_audio), sampling_rate=16000)
            if arr is not None and len(arr) > 0:
                audios_decodificados.append(arr)
        except Exception:
            pass

    if not audios_decodificados:
        raise ValueError(f"No fue posible decodificar ningún archivo de audio en: {p_carpeta}")

    concatenado = np.concatenate(audios_decodificados)
    if len(concatenado) == 0:
        raise ValueError("El audio concatenado está vacío.")

    muestras_objetivo = int(duracion_objetivo_s * 16000)
    if len(concatenado) < muestras_objetivo:
        repeticiones = math.ceil(muestras_objetivo / len(concatenado))
        concatenado = np.tile(concatenado, repeticiones)

    concatenado = concatenado[:muestras_objetivo]
    return concatenado.astype(np.float32)


def ejecutar_evaluacion_velocidad(
    audios_dir: str | Path | None = None,
    audio_path: str | Path | None = None,
    modelos: Sequence[str] | None = None,
    duracion_segundos: float = 300.0,
    compute_type: str = "int8",
    device: str = "cpu",
    vad: bool = True,
    simulado: bool = False,
) -> dict[str, Any]:
    """Ejecuta la medición de RTF, memoria RSS y conteo de palabras para los modelos especificados.

    Soporta:
    - --audios <carpeta>: Concatena voz real en memoria RAM hasta duracion_segundos.
    - --audio <archivo>: Medición con archivo único.
    - Modo simulado (por defecto si no se pasan audios reales): emite aviso 'SIMULADO: no es una medición'.
    """
    lista_modelos = list(modelos) if modelos else ["base", "small", "large-v3-turbo"]
    es_audio_temporal = False
    ruta_audio_efectiva: Path | None = None
    audio_memoria: np.ndarray | None = None

    # Si no se pasó ni carpeta de audios ni archivo de audio individual, forzar modo simulado
    if audios_dir is None and audio_path is None and not simulado:
        simulado = True

    if not simulado:
        if audios_dir is not None:
            audio_memoria = cargar_y_concatenar_audios(audios_dir, duracion_objetivo_s=duracion_segundos)
            duracion_audio = len(audio_memoria) / 16000.0
            descripcion_audio = f"directorio:{audios_dir} (en memoria RAM)"
        elif audio_path is not None:
            ruta_audio_efectiva = Path(audio_path).resolve()
            if not ruta_audio_efectiva.exists():
                raise FileNotFoundError(f"No se encontró el audio especificado en: {ruta_audio_efectiva}")
            duracion_audio = obtener_duracion_audio(ruta_audio_efectiva)
            if duracion_audio <= 0:
                duracion_audio = duracion_segundos
            descripcion_audio = str(ruta_audio_efectiva)
        else:
            ruta_audio_efectiva = generar_audio_sintetico(duracion_segundos=duracion_segundos)
            es_audio_temporal = True
            duracion_audio = duracion_segundos
            descripcion_audio = "<sintetico_temporal>"
    else:
        duracion_audio = duracion_segundos
        descripcion_audio = f"<simulado_{int(duracion_audio)}s>"

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
                palabras_sim = int(duracion_audio * 2.5)  # ~150 palabras/min

                resultados_modelos[modelo_limpio] = {
                    "tiempo_carga_s": round(t_carga, 3),
                    "tiempo_transcripcion_s": round(t_transcripcion, 3),
                    "rtf": round(rtf, 4),
                    "minutos_por_hora": round(min_h, 2),
                    "ram_rss_mb": round(ram_mb, 1),
                    "palabras_transcritas": palabras_sim,
                    "valida": True,
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
                entrada_whisper: Any = audio_memoria if audio_memoria is not None else str(ruta_audio_efectiva)
                segmentos, info = modelo_whisper.transcribe(
                    entrada_whisper,
                    language="es",
                    vad_filter=vad,
                    temperature=0.0,
                )
                # Iterar completamente el generador y extraer palabras
                textos = [s.text for s in segmentos]
                tiempo_transcripcion_s = time.perf_counter() - t0_trans
                total_palabras = sum(len(t.split()) for t in textos)

                duracion_efectiva = (
                    info.duration
                    if hasattr(info, "duration") and info.duration and info.duration > 0
                    else duracion_audio
                )
                rtf, min_h = calcular_rtf(tiempo_transcripcion_s, duracion_efectiva)
                ram_rss = obtener_ram_rss_mb()
                eval_h2 = evaluar_hipotesis_h2(rtf)
                es_valida = total_palabras > 0

                veredicto = eval_h2["veredicto"].value if es_valida else "INVALIDA"
                motivo = (
                    eval_h2["motivo"]
                    if es_valida
                    else "Medición inválida: 0 palabras transcritas (audio descartado por VAD o sin voz)."
                )

                resultados_modelos[modelo_limpio] = {
                    "tiempo_carga_s": round(tiempo_carga_s, 3),
                    "tiempo_transcripcion_s": round(tiempo_transcripcion_s, 3),
                    "rtf": round(rtf, 4),
                    "minutos_por_hora": round(min_h, 2),
                    "ram_rss_mb": round(ram_rss, 1),
                    "palabras_transcritas": total_palabras,
                    "valida": es_valida,
                    "veredicto_h2": veredicto,
                    "motivo": motivo,
                }

        # Veredicto general pre-registrado en H2 (basado en 'small')
        if "small" in resultados_modelos:
            veredicto_general = resultados_modelos["small"]["veredicto_h2"]
        elif resultados_modelos:
            primer_modelo = next(iter(resultados_modelos))
            veredicto_general = resultados_modelos[primer_modelo]["veredicto_h2"]
        else:
            veredicto_general = VeredictoH2.INTERMEDIA.value

        medicion_valida = all(m.get("valida", True) for m in resultados_modelos.values())

        return {
            "audio": descripcion_audio,
            "duracion_audio_s": round(duracion_audio, 2),
            "device": device,
            "compute_type": compute_type,
            "vad": vad,
            "simulado": simulado,
            "medicion_valida": medicion_valida,
            "modelos": resultados_modelos,
            "veredicto_general_h2": veredicto_general,
        }

    finally:
        if es_audio_temporal and ruta_audio_efectiva is not None and ruta_audio_efectiva.exists():
            try:
                ruta_audio_efectiva.unlink()
            except OSError:
                pass


def formatear_tabla_resultados(datos: dict[str, Any]) -> str:
    """Genera la representación tabular formateada de los resultados para la terminal."""
    lineas: list[str] = []

    if datos.get("simulado"):
        lineas.append("\n" + "=" * 90)
        lineas.append("  SIMULADO: no es una medición")
        lineas.append("  [ADVERTENCIA] Ejecución simulada. Pase --audios <carpeta> para medir con voz real.")
        lineas.append("=" * 90)

    lineas.append(
        f"\nAudio evaluado: {datos.get('audio')} | "
        f"Duración: {datos.get('duracion_audio_s')}s | "
        f"Device: {datos.get('device')} | "
        f"Compute: {datos.get('compute_type')} | "
        f"VAD: {datos.get('vad')}\n"
    )

    encabezado = (
        f"{'Modelo':<18} | {'Carga (s)':<10} | {'Trans (s)':<10} | "
        f"{'RTF':<8} | {'Min/h':<8} | {'RAM (MB)':<10} | {'Palabras':<10} | {'Veredicto H2':<12}"
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
            f"{metricas.get('palabras_transcritas', 0):<10} | "
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
        "--audios",
        type=str,
        default=None,
        help="Ruta a una carpeta con archivos de audio para concatenar en memoria RAM (~5 min).",
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
        help="Duración en segundos del audio (default: 30.0 s para sintético, 300.0 s / 5 min para --audios).",
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

    # Si no se pasó --audios ni --audio, se activa el modo simulado automáticamente
    es_simulado = args.simulado or (args.audios is None and args.audio is None)
    duracion_efectiva = 300.0 if (args.audios and args.duracion == 30.0) else args.duracion

    try:
        resultados = ejecutar_evaluacion_velocidad(
            audios_dir=args.audios,
            audio_path=args.audio,
            modelos=modelos_lista,
            duracion_segundos=duracion_efectiva,
            compute_type=args.compute_type,
            device=args.device,
            vad=args.vad,
            simulado=es_simulado,
        )
    except Exception as err:
        print(f"\n[ERROR] Error durante la evaluación de velocidad: {err}", file=sys.stderr)
        return 1

    tabla = formatear_tabla_resultados(resultados)
    print(tabla)

    if args.salida:
        p_salida = Path(args.salida).resolve()
        p_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(p_salida, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        print(f"Resultados guardados en: {p_salida}")

    if not resultados.get("medicion_valida", True):
        print("\n[ERROR] Medición INVÁLIDA: se transcribieron 0 palabras.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

