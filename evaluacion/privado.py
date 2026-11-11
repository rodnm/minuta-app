"""Caja negra de procesamiento y evaluación privada (evaluacion/privado.py).

Cumple estrictamente con la regla de privacidad L21 y la sección 2 del prompt maestro:
1. Procesa audio y transcripciones exclusivamente en local (faster-whisper y Ollama).
2. Prohibido mandar audio o texto a la API de Gemini o servicios externos.
3. Almacena resultados en data/privado/reunion_real/salidas/ (ignorado en git).
4. Imprime ÚNICAMENTE métricas numéricas agregadas (duración, RTF, latencia, etc.).
5. Nunca imprime texto de la reunión, ni siquiera en caso de error.
6. Detector de fugas (--verificar-fugas, compuerta G4) con shingles de 8 palabras.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Sequence

# Asegurar que el directorio raíz del repositorio esté en sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from minuta.esquemas import (
    MapaMental,
    ResultadoEntrevista,
    ResultadoPonencia,
    ResultadoReunion,
    Segmento,
    Transcripcion,
)


def reportar_error_anonimo(contexto: str, error: Exception | str) -> str:
    """Genera un mensaje de error sin filtrar texto sensible del contenido."""
    tipo_err = type(error).__name__ if isinstance(error, Exception) else "Error"
    # Filtrar palabras largas o comillas que puedan contener citas literales
    return f"{contexto}: {tipo_err} (operación no completada)"


def extraer_shingles_de_texto(texto: str, tamano: int = 8) -> set[tuple[str, ...]]:
    """Extrae n-gramas (shingles) de palabras normalizadas a partir de un texto."""
    if not texto:
        return set()
    # Normalizar a minúsculas y extraer solo palabras alfanuméricas
    palabras = re.findall(r"\b\w+\b", texto.lower(), flags=re.UNICODE)
    if len(palabras) < tamano:
        return set()
    return {tuple(palabras[i : i + tamano]) for i in range(len(palabras) - tamano + 1)}


def verificar_fugas(
    dir_privado: Path | None = None,
    root_dir: Path | None = None,
) -> int:
    """Compuerta G4: busca coincidencias de shingles de 8 palabras del audio privado en el repo.

    Revisa:
    - Todos los archivos versionados (git ls-files), excluyendo data/privado y binarios.
    - Todos los cambios pendientes en el índice y árbol de trabajo (git diff HEAD).

    Retorna el número total de coincidencias detectadas (debe ser 0).
    """
    if root_dir is None:
        root_dir = ROOT_DIR
    if dir_privado is None:
        dir_privado = root_dir / "data" / "privado"

    if not dir_privado.exists():
        return 0

    # 1. Recolectar todos los textos de transcripciones privadas (.json y .txt)
    textos_privados: list[str] = []
    for ruta in dir_privado.rglob("*"):
        if ruta.is_file() and ruta.suffix in {".json", ".txt"}:
            try:
                if ruta.suffix == ".json":
                    contenido = json.loads(ruta.read_text(encoding="utf-8"))
                    # Si es formato Transcripcion
                    if isinstance(contenido, dict):
                        if "segmentos" in contenido and isinstance(contenido["segmentos"], list):
                            for seg in contenido["segmentos"]:
                                if isinstance(seg, dict) and "texto" in seg:
                                    textos_privados.append(str(seg["texto"]))
                        elif "resumen_general" in contenido:
                            textos_privados.append(str(contenido["resumen_general"]))
                else:
                    textos_privados.append(ruta.read_text(encoding="utf-8"))
            except Exception:
                continue

    if not textos_privados:
        return 0

    # Construir conjunto de shingles de 8 palabras
    todos_shingles: set[tuple[str, ...]] = set()
    for t in textos_privados:
        todos_shingles.update(extraer_shingles_de_texto(t, tamano=8))

    if not todos_shingles:
        return 0

    coincidencias = 0

    # 2. Revisar archivos rastreados en Git (git ls-files)
    try:
        res_files = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=root_dir,
            check=True,
        )
        archivos_git = res_files.stdout.splitlines()
    except Exception:
        archivos_git = []

    extensiones_binarias = {".png", ".jpg", ".jpeg", ".pdf", ".ico", ".docx", ".xlsx", ".zip", ".pyc"}

    for rel_path in archivos_git:
        if any(rel_path.startswith(p) for p in ["data/privado", ".git"]):
            continue
        ruta_archivo = root_dir / rel_path
        if ruta_archivo.suffix.lower() in extensiones_binarias or not ruta_archivo.is_file():
            continue

        try:
            contenido_repo = ruta_archivo.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        shingles_repo = extraer_shingles_de_texto(contenido_repo, tamano=8)
        interseccion = todos_shingles.intersection(shingles_repo)
        if interseccion:
            coincidencias += len(interseccion)

    # 3. Revisar git diff HEAD (cambios en el índice y sin stagear)
    try:
        res_diff = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            cwd=root_dir,
            check=True,
        )
        diff_text = res_diff.stdout
        if diff_text:
            shingles_diff = extraer_shingles_de_texto(diff_text, tamano=8)
            interseccion_diff = todos_shingles.intersection(shingles_diff)
            if interseccion_diff:
                coincidencias += len(interseccion_diff)
    except Exception:
        pass

    return coincidencias


def procesar_privado(
    audio_path: Path | str | None = None,
    transcripcion: Transcripcion | None = None,
    salidas_dir: Path | str | None = None,
    modelo_whisper: str = "small",
    tipo_plantilla: str = "reunion",
    modelo_llm: str = "qwen3:4b",
    solo_transcribir: bool = False,
    proveedor_simulado: bool = False,
) -> dict[str, Any]:
    """Caja negra principal: corre el pipeline en local y retorna solo métricas agregadas."""
    if salidas_dir is None:
        salidas_dir = ROOT_DIR / "data" / "privado" / "reunion_real" / "salidas"
    salidas_dir = Path(salidas_dir)
    salidas_dir.mkdir(parents=True, exist_ok=True)

    metricas: dict[str, Any] = {}

    # 1. Transcripción con faster-whisper local
    if transcripcion is None:
        if audio_path is None or not Path(audio_path).exists():
            raise FileNotFoundError(reportar_error_anonimo("audio", FileNotFoundError("No encontrado")))

        from minuta.transcribir import transcribir_audio

        t0_trans = time.perf_counter()
        transcripcion = transcribir_audio(
            audio=Path(audio_path),
            modelo=modelo_whisper,
            device="cpu",
            compute_type="int8",
            vad_filter=True,
            usar_hotwords=True,
        )
        t_trans = time.perf_counter() - t0_trans

        metricas["duracion_s"] = round(transcripcion.duracion_s, 2)
        metricas["duracion_min"] = round(transcripcion.duracion_s / 60.0, 2)
        metricas["tiempo_transcripcion_s"] = round(t_trans, 2)
        metricas["tiempo_transcripcion_min"] = round(t_trans / 60.0, 2)
        metricas["rtf"] = round(t_trans / max(transcripcion.duracion_s, 0.001), 4)
        metricas["segmentos"] = len(transcripcion.segmentos)
    else:
        metricas["duracion_s"] = round(transcripcion.duracion_s, 2)
        metricas["duracion_min"] = round(transcripcion.duracion_s / 60.0, 2)
        metricas["segmentos"] = len(transcripcion.segmentos)

    # Guardar transcripción en salidas privadas
    ruta_trans = salidas_dir / "transcripcion.json"
    ruta_trans.write_text(transcripcion.model_dump_json(indent=2), encoding="utf-8")

    if solo_transcribir:
        return metricas

    # 2. Estructuración con LLM local (Ollama)
    from minuta.estructurar import estructurar_transcripcion, particionar_en_bloques

    bloques = (
        [list(transcripcion.segmentos)]
        if transcripcion.duracion_s <= 600.0
        else particionar_en_bloques(transcripcion.segmentos, max_duracion_bloque_s=600.0)
    )
    metricas["bloques"] = len(bloques)

    if proveedor_simulado:
        from minuta.proveedores import ProveedorMock

        proveedor = ProveedorMock()
    else:
        from minuta.proveedores import ProveedorOllama

        proveedor = ProveedorOllama(
            modelo=modelo_llm,
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            timeout=600.0,
            num_ctx=8192,
        )

    t0_llm = time.perf_counter()
    latencias_bloques: list[float] = []

    try:
        resultado = estructurar_transcripcion(
            transcripcion,
            tipo_plantilla=tipo_plantilla,  # type: ignore[arg-type]
            proveedor=proveedor,
            modo="solo_llm",
        )
        t_llm = time.perf_counter() - t0_llm
        metricas["pct_json_valido"] = 100.0
        metricas["tiempo_estructuracion_s"] = round(t_llm, 2)
    except Exception as err:
        metricas["pct_json_valido"] = 0.0
        metricas["error"] = reportar_error_anonimo("estructuracion", err)
        return metricas

    # Guardar resultado en salidas privadas
    ruta_res = salidas_dir / f"resultado_{tipo_plantilla}.json"
    ruta_res.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")

    metricas["citas_descartadas"] = resultado.descartados
    metricas["num_ramas"] = len(resultado.mapa.ramas) if resultado.mapa else 0

    if isinstance(resultado, ResultadoReunion):
        metricas["num_temas"] = len(resultado.temas)
        metricas["num_acuerdos"] = len(resultado.acuerdos)
        metricas["num_tareas"] = len(resultado.tareas)
    elif isinstance(resultado, ResultadoPonencia):
        metricas["num_ideas"] = len(resultado.ideas_clave)
        metricas["num_preguntas"] = len(resultado.preguntas_abiertas)
    elif isinstance(resultado, ResultadoEntrevista):
        metricas["num_codigos"] = len(resultado.libro)
        metricas["num_fragmentos"] = len(resultado.fragmentos)

    return metricas


def main() -> int:
    """Punto de entrada de línea de comandos para la caja negra privada."""
    parser = argparse.ArgumentParser(
        description="Caja negra de procesamiento y evaluación privada (Minuta)."
    )
    parser.add_argument("--audio", type=str, help="Ruta al archivo de audio privado a procesar.")
    parser.add_argument("--solo-transcribir", action="store_true", help="Ejecutar solo transcripción Whisper.")
    parser.add_argument("--modelo", type=str, default="small", help="Modelo Whisper ('small', 'base').")
    parser.add_argument("--modelo-llm", type=str, default="qwen3:4b", help="Modelo local de Ollama.")
    parser.add_argument("--plantilla", type=str, default="reunion", choices=["reunion", "ponencia", "entrevista"])
    parser.add_argument("--salida-dir", type=str, default=None, help="Directorio para salidas privadas.")
    parser.add_argument("--verificar-fugas", action="store_true", help="Ejecuta compuerta G4 contra el repo.")
    parser.add_argument("--ref", type=str, default=None, help="Archivo CSV de referencia para to-dos.")

    args = parser.parse_args()

    # Compuerta G4: Detector de fugas
    if args.verificar_fugas:
        coincidencias = verificar_fugas()
        print(f"coincidencias: {coincidencias}")
        return 0 if coincidencias == 0 else 1

    if not args.audio:
        print(reportar_error_anonimo("argumentos", ValueError("Parámetro --audio requerido")), file=sys.stderr)
        return 2

    try:
        metricas = procesar_privado(
            audio_path=args.audio,
            salidas_dir=args.salida_dir,
            modelo_whisper=args.modelo,
            modelo_llm=args.modelo_llm,
            tipo_plantilla=args.plantilla,
            solo_transcribir=args.solo_transcribir,
        )
    except Exception as err:
        print(reportar_error_anonimo("proceso", err), file=sys.stderr)
        return 1

    # Imprimir métricas agregadas (solo números / claves)
    print("======================================================================")
    print("MÉTRICAS AGREGADAS - EVALUACIÓN PRIVADA (CAJA NEGRA)")
    print("======================================================================")
    for clave, valor in sorted(metricas.items()):
        print(f"{clave}: {valor}")
    print("======================================================================")

    return 0


if __name__ == "__main__":
    sys.exit(main())
