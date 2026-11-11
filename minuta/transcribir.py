"""Módulo de transcripción acústica con faster-whisper y glosario en hotwords (minuta/transcribir.py).

Implementa la transcripción en español (language="es", vad_filter=True, compute_type="int8"),
con inyección recurrente de términos de investigación vía hotwords, almacenamiento
de caché fuera del repositorio y estructuración según el contrato Pydantic v2 (Transcripcion).

ESTRICTAMENTE PROHIBIDO importar nada desde evaluacion/.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, BinaryIO, Sequence, Union

from faster_whisper import WhisperModel

from minuta.compat import (
    aplicar_parches_compatibilidad,
    obtener_directorio_whisper_cache,
)
from minuta.esquemas import Segmento, Transcripcion
from minuta.glosario import formatear_hotwords, normalizar_glosario

logger = logging.getLogger(__name__)


def cargar_modelo_whisper(
    modelo: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
) -> WhisperModel:
    """Carga un modelo faster-whisper con la caché fuera del repositorio.

    La app lo envuelve en ``st.cache_resource`` para cargarlo una sola vez por proceso
    y lo pasa a ``transcribir_audio(modelo_cargado=...)``.
    """
    aplicar_parches_compatibilidad()
    return WhisperModel(
        modelo,
        device=device,
        compute_type=compute_type,
        download_root=obtener_directorio_whisper_cache(),
    )


def transcribir_audio(
    audio: Union[str, Path, BinaryIO],
    modelo: str = "small",
    glosario_adicional: list[str] | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
    vad_filter: bool = True,
    usar_hotwords: bool = True,
    audio_id: str | None = None,
    modelo_cargado: WhisperModel | None = None,
) -> Transcripcion:
    """Transcribe un archivo de audio usando faster-whisper con glosario de investigación.

    Parámetros:
    - audio: Ruta del archivo (str o Path) o stream binario.
    - modelo: Identificador del modelo Whisper ('tiny', 'base', 'small', 'medium', 'large-v3-turbo').
    - glosario_adicional: Lista opcional de términos adicionales del usuario.
    - device: Dispositivo de cómputo ('cpu' o 'cuda').
    - compute_type: Cuantización de pesos ('int8', 'float16', 'float32').
    - vad_filter: Si True, activa Silero VAD para filtrar pausas y ruidos.
    - usar_hotwords: Si True, inyecta el glosario de investigación en cada ventana de 30 s.
    - audio_id: Identificador opcional para el objeto Transcripcion.
    - modelo_cargado: Modelo ya cargado con ``cargar_modelo_whisper`` (por ejemplo, desde la
      caché de la app). Si es None, se carga uno nuevo con ``modelo``, ``device`` y ``compute_type``.

    Retorna:
    - Objeto Transcripcion validado con Pydantic v2.
    """
    # 1. Asegurar parches de compatibilidad de bajo nivel
    aplicar_parches_compatibilidad()

    # 2-3. Preparar glosario y hotwords (la caché del modelo se resuelve en cargar_modelo_whisper)
    glosario_completo = normalizar_glosario(glosario_adicional)
    hotwords_str: str | None = None
    if usar_hotwords:
        hotwords_str = formatear_hotwords(glosario_completo)
        if not hotwords_str:
            hotwords_str = None

    # 4. Determinar identificador de audio
    if audio_id is None:
        if isinstance(audio, (str, Path)):
            audio_id = Path(audio).stem
        else:
            audio_id = "audio"

    # 5. Cargar modelo Whisper, salvo que ya venga cargado
    whisper_model = modelo_cargado
    if whisper_model is None:
        whisper_model = cargar_modelo_whisper(modelo, device=device, compute_type=compute_type)

    # 6. Ejecutar transcripción determinista (temperature 0, idioma español)
    audio_param = str(audio) if isinstance(audio, Path) else audio
    segmentos_iter, info = whisper_model.transcribe(
        audio_param,
        language="es",
        temperature=0.0,
        vad_filter=vad_filter,
        hotwords=hotwords_str,
    )

    # 7. Mapear segmentos a modelos Pydantic
    segmentos_lista: list[Segmento] = []
    for idx, seg in enumerate(segmentos_iter, start=1):
        texto_limpio = seg.text.strip()
        if not texto_limpio:
            continue
        inicio = round(float(seg.start), 2)
        fin = round(float(seg.end), 2)
        if fin < inicio:
            fin = inicio
        segmentos_lista.append(
            Segmento(
                id=seg.id if getattr(seg, "id", None) is not None else idx,
                inicio_s=inicio,
                fin_s=fin,
                texto=texto_limpio,
                orador="Hablante",
            )
        )

    # 8. Calcular duración total
    duracion = 0.0
    if hasattr(info, "duration") and info.duration is not None and info.duration > 0:
        duracion = round(float(info.duration), 2)
    elif segmentos_lista:
        duracion = max(s.fin_s for s in segmentos_lista)

    return Transcripcion(
        audio_id=audio_id,
        duracion_s=duracion,
        modelo=modelo,
        glosario=glosario_completo,
        segmentos=segmentos_lista,
    )


def _cargar_terminos_glosario_cli(arg_glosario: str | None) -> list[str] | None:
    """Parsea el argumento --glosario desde archivo o cadena separada por comas."""
    if not arg_glosario:
        return None

    path_posible = Path(arg_glosario)
    if path_posible.is_file():
        try:
            contenido = path_posible.read_text(encoding="utf-8")
            # Probar si es JSON
            datos = json.loads(contenido)
            if isinstance(datos, list):
                return [str(item) for item in datos]
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        # Leer línea por línea
        lineas = path_posible.read_text(encoding="utf-8").splitlines()
        return [lin.strip() for lin in lineas if lin.strip()]

    # Tratar como lista separada por comas
    return [t.strip() for t in arg_glosario.split(",") if t.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de línea de comandos para transcripción de Minuta."""
    parser = argparse.ArgumentParser(
        description="Transcribe audio con faster-whisper y glosario de investigación para Minuta.",
        prog="python -m minuta.transcribir",
    )
    parser.add_argument("audio", type=str, help="Ruta al archivo de audio (.m4a, .mp3, .wav, etc.)")
    parser.add_argument(
        "--modelo",
        type=str,
        default="small",
        help="Modelo Whisper a utilizar (por defecto: small)",
    )
    parser.add_argument(
        "-o",
        "--salida",
        type=str,
        default=None,
        help="Ruta de destino para guardar el JSON estructurado (opcional)",
    )
    parser.add_argument(
        "--glosario",
        type=str,
        default=None,
        help="Términos adicionales separados por coma o ruta a archivo de texto con un término por línea",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Dispositivo de ejecución ('cpu' o 'cuda', por defecto: cpu)",
    )
    parser.add_argument(
        "--compute-type",
        type=str,
        default="int8",
        help="Tipo de cuantización ('int8', 'float16', 'float32', por defecto: int8)",
    )
    parser.add_argument(
        "--sin-hotwords",
        action="store_true",
        help="Desactiva la inyección de hotwords en Whisper",
    )
    parser.add_argument(
        "--sin-vad",
        action="store_true",
        help="Desactiva el filtro VAD (Silero)",
    )

    args = parser.parse_args(argv)

    ruta_audio = Path(args.audio)
    if not ruta_audio.exists():
        print(f"Error: No se encontró el archivo de audio '{args.audio}'.", file=sys.stderr)
        return 1

    terminos_adicionales = _cargar_terminos_glosario_cli(args.glosario)

    try:
        tx = transcribir_audio(
            audio=ruta_audio,
            modelo=args.modelo,
            glosario_adicional=terminos_adicionales,
            device=args.device,
            compute_type=args.compute_type,
            vad_filter=not args.sin_vad,
            usar_hotwords=not args.sin_hotwords,
        )
    except Exception as e:
        print(f"Error durante la transcripción: {e}", file=sys.stderr)
        return 1

    json_salida = tx.model_dump_json(indent=2)

    if args.salida:
        ruta_salida = Path(args.salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ruta_salida.write_text(json_salida, encoding="utf-8")
        print(
            f"Transcripción exitosa guardada en '{ruta_salida}' "
            f"({len(tx.segmentos)} segmentos, duración {tx.duracion_s:.1f} s)."
        )
    else:
        print(json_salida)

    return 0


if __name__ == "__main__":
    sys.exit(main())
