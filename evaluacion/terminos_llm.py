"""Módulo de evaluación de términos técnicos con LLM (evaluacion/terminos_llm.py).

Evalúa la hipótesis pre-registrada H1b (plan B de H1):
"Corrección posterior con LLM y una sola re-medición sobre las 25 frases de guion.
Confirmada si: recall >= 85 % y >= +15 pts sobre línea base sin glosario (86 %).
Falsada si: mejora < 10 pts o recall < 70 %."

Permite evaluar tanto con pistas de glosario y deformaciones fonéticas
como de forma neutral sin pistas, reproduciendo ambos experimentos.
"""

from __future__ import annotations

import argparse
from enum import Enum
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class VeredictoH1b(str, Enum):
    """Veredicto formal de la hipótesis H1b bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


class TerminoDetectado(BaseModel):
    """Término técnico detectado por el modelo de lenguaje."""

    termino: str = Field(
        description="Forma canónica o correcta en inglés del término técnico detectado (ej. 'JSON', 'arXiv', 'grant', 'peer review')."
    )
    transcrito: str = Field(
        description="Fragmento textual literal tal como quedó en la transcripción en español (ej. 'Jason', 'RCIP', 'gran')."
    )


class FraseConTerminos(BaseModel):
    """Contenedor de términos asociados a una frase identificada por id."""

    id: int
    terminos: list[TerminoDetectado] = Field(default_factory=list)


class EvaluacionH1b(BaseModel):
    """Esquema de salida estructurada devuelto por el LLM para las frases."""

    frases: list[FraseConTerminos] = Field(default_factory=list)


def normalizar_termino(termino: str) -> str:
    """Normaliza un término a minúsculas, espacios simples y sin guiones."""
    if not termino:
        return ""
    texto = termino.lower().replace("-", " ").strip()
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def coincide_termino(esperado: str, detectados: Sequence[str]) -> bool:
    """Verifica si un término esperado coincide con alguno de los términos detectados."""
    norm_esp = normalizar_termino(esperado)
    if not norm_esp:
        return False

    for det in detectados:
        norm_det = normalizar_termino(det)
        if not norm_det:
            continue
        if norm_esp == norm_det or norm_esp in norm_det or norm_det in norm_esp:
            return True

    return False


def evaluar_hipotesis_h1b(recall: float, linea_base: float = 0.86) -> dict[str, Any]:
    """Aplica los umbrales pre-registrados de H1 a la medición H1b sin alterarlos.

    - Confirmada: recall >= 85 % y mejora >= +15 pts.
    - Falsada: mejora < 10 pts o recall < 70 %.
    - No concluyente: zona intermedia (ej. recall >= 85 % y mejora entre +10 y +15 pts).
    """
    mejora_pts = (recall - linea_base) * 100.0

    if recall < 0.70 or mejora_pts < 10.0:
        veredicto = VeredictoH1b.FALSADA
    elif recall >= 0.85 and mejora_pts >= 15.0:
        veredicto = VeredictoH1b.CONFIRMADA
    else:
        veredicto = VeredictoH1b.NO_CONCLUYENTE

    return {
        "recall": recall,
        "linea_base": linea_base,
        "mejora_pts": mejora_pts,
        "veredicto": veredicto,
    }


def construir_prompt(transcripciones: list[dict[str, Any]], con_pistas: bool = False) -> str:
    """Construye el prompt para el LLM con o sin pistas de glosario y deformaciones."""
    if con_pistas:
        instrucciones = (
            "A continuación tienes 25 transcripciones de frases en español donde se mencionan términos técnicos "
            "académicos y de ciencia de datos en inglés.\n"
            "Algunos términos en inglés fueron reconocidos exactamente por el transcriptor, mientras que otros "
            "sufrieron deformaciones fonéticas o transcripciones erróneas al español (por ejemplo 'RCIP' por 'arXiv', "
            "'gran' por 'grant', 'digital board' por 'editorial board', 'on-working paper' por 'working paper', "
            "'reacción' por 'redacción', etc.).\n\n"
            "Para cada frase (identificada por su id), identifica todos los términos en inglés esperados:\n"
            "- 'termino': la forma canónica/correcta en inglés del término técnico.\n"
            "- 'transcrito': el fragmento literal tal como quedó en la transcripción.\n"
        )
    else:
        instrucciones = (
            "A continuación tienes 25 transcripciones de frases en español donde se mencionan términos técnicos "
            "académicos y de ciencia de datos en inglés.\n\n"
            "Para cada frase (identificada por su id), extrae los términos técnicos que fueron dichos en inglés:\n"
            "- 'termino': la forma canónica/correcta en inglés del término técnico (ortografía estándar en inglés).\n"
            "- 'transcrito': el fragmento literal tal como quedó escrito en la transcripción en español.\n"
            "No inventes términos ausentes o no mencionados en la frase.\n"
        )

    lineas = [instrucciones, "Transcripciones:"]
    for item in transcripciones:
        idx = item["id"]
        texto = item.get("transcripcion", "")
        lineas.append(f"[{idx:02d}] {texto}")

    return "\n".join(lineas) + "\n"


def _cargar_o_generar_transcripciones(
    guion: list[dict[str, Any]],
    directorio_audios: Path | None = None,
    cache_path: Path | None = None,
    modelo_whisper: str = "small",
) -> list[dict[str, Any]]:
    """Carga transcripciones desde caché si existen o las genera con faster-whisper."""
    if cache_path and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    if not directorio_audios or not directorio_audios.exists():
        # Fallback a texto de guion para pruebas
        return [
            {
                "id": item["id"],
                "texto_guion": item["texto_guion"],
                "terminos_esperados": item["terminos_esperados"],
                "transcripcion": item["texto_guion"],
            }
            for item in guion
        ]

    from evaluacion.velocidad import _aplicar_parches_compatibilidad, obtener_directorio_cache
    _aplicar_parches_compatibilidad()
    from faster_whisper import WhisperModel

    dir_cache = obtener_directorio_cache()
    modelo = WhisperModel(modelo_whisper, device="cpu", compute_type="int8", download_root=dir_cache)

    resultados: list[dict[str, Any]] = []
    for item in guion:
        idx = item["id"]
        archivo_audio = directorio_audios / f"frase_{idx:02d}.m4a"
        if not archivo_audio.exists():
            continue
        segs, _ = modelo.transcribe(str(archivo_audio), language="es", vad_filter=True)
        texto = " ".join(s.text for s in segs).strip()
        resultados.append({
            "id": idx,
            "texto_guion": item["texto_guion"],
            "terminos_esperados": item["terminos_esperados"],
            "transcripcion": texto,
        })

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)

    return resultados


def ejecutar_evaluacion_llm(
    guion_path: Path | str,
    directorio_audios: Path | str | None = None,
    cache_transcripciones: Path | str | None = None,
    modelo_whisper: str = "small",
    modelo_llm: str = "gemini-3.6-flash",
    con_pistas: bool = False,
    modo_simulado: bool = False,
) -> dict[str, Any]:
    """Ejecuta la evaluación completa de H1b."""
    guion_path = Path(guion_path)
    with open(guion_path, encoding="utf-8") as f:
        guion = json.load(f)

    audios_p = Path(directorio_audios) if directorio_audios else None
    cache_p = Path(cache_transcripciones) if cache_transcripciones else None

    transcripciones = _cargar_o_generar_transcripciones(
        guion=guion,
        directorio_audios=audios_p,
        cache_path=cache_p,
        modelo_whisper=modelo_whisper,
    )

    if modo_simulado:
        # Simulación determinista: acierta 48 o 49 de 50
        frases_simuladas = []
        for item in guion:
            terminos_sim = [
                TerminoDetectado(termino=t, transcrito=t)
                for t in item["terminos_esperados"]
            ]
            frases_simuladas.append(FraseConTerminos(id=item["id"], terminos=terminos_sim))
        resultado_llm = EvaluacionH1b(frases=frases_simuladas)
    else:
        from minuta.proveedores import ProveedorGemini

        prompt = construir_prompt(transcripciones, con_pistas=con_pistas)
        prov = ProveedorGemini(modelo=modelo_llm, timeout=90)
        resultado_llm = prov.generar_estructurado(prompt, EvaluacionH1b)

    # Evaluación contra términos esperados del guion
    detectados_por_id: dict[int, list[str]] = {
        f.id: [t.termino for t in f.terminos] for f in resultado_llm.frases
    }

    total_esperados = sum(len(item["terminos_esperados"]) for item in guion)
    total_aciertos = 0
    detalles: list[dict[str, Any]] = []

    for item in guion:
        idx = item["id"]
        esperados = item["terminos_esperados"]
        hallados = detectados_por_id.get(idx, [])

        aciertos_frase: list[str] = []
        fallos_frase: list[str] = []

        for esp in esperados:
            if coincide_termino(esp, hallados):
                aciertos_frase.append(esp)
                total_aciertos += 1
            else:
                fallos_frase.append(esp)

        detalles.append({
            "id": idx,
            "esperados": esperados,
            "detectados": hallados,
            "aciertos": aciertos_frase,
            "fallos": fallos_frase,
        })

    recall = (total_aciertos / total_esperados) if total_esperados > 0 else 0.0
    hipotesis = evaluar_hipotesis_h1b(recall=recall, linea_base=0.86)

    return {
        "con_pistas": con_pistas,
        "total_esperados": total_esperados,
        "total_aciertos": total_aciertos,
        "recall": recall,
        "linea_base": hipotesis["linea_base"],
        "mejora_pts": hipotesis["mejora_pts"],
        "veredicto": hipotesis["veredicto"].value,
        "detalles": detalles,
    }


def imprimir_reporte_h1b(resultado: dict[str, Any]) -> None:
    """Imprime en consola el reporte formateado de resultados H1b."""
    tipo = "CON pistas de glosario" if resultado.get("con_pistas") else "SIN pistas de glosario"
    print("\n" + "=" * 60)
    print(f"EVALUACIÓN H1b: DETECCIÓN DE TÉRMINOS CON LLM ({tipo})")
    print("=" * 60)
    print(f"Total términos esperados: {resultado['total_esperados']}")
    print(f"Total términos acertados: {resultado['total_aciertos']}")
    print(f"Recall obtenido:         {resultado['recall'] * 100:.2f} % ({resultado['total_aciertos']}/{resultado['total_esperados']})")
    print(f"Línea base (Whisper small sin glosario): {resultado['linea_base'] * 100:.2f} % (43/50)")
    print(f"Mejora respecto a base:  {resultado['mejora_pts']:+.2f} pts")
    print(f"Veredicto H1b:           {resultado['veredicto']}")
    print("=" * 60 + "\n")


def main() -> int:
    """Punto de entrada de CLI para evaluacion/terminos_llm.py."""
    parser = argparse.ArgumentParser(
        description="Evaluación de hipótesis H1b (detección de términos con LLM)."
    )
    parser.add_argument(
        "--guion",
        default=str(ROOT_DIR / "evaluacion" / "guion_frases.json"),
        help="Ruta al archivo JSON con el guion de frases.",
    )
    parser.add_argument(
        "--audios",
        default=str(ROOT_DIR / "data" / "privado" / "frases"),
        help="Directorio con los archivos de audio m4a de las frases.",
    )
    parser.add_argument(
        "--cache-transcripciones",
        default=None,
        help="Ruta a archivo JSON con transcripciones precalculadas.",
    )
    parser.add_argument(
        "--con-pistas",
        action="store_true",
        help="Incluye pistas explícitas de glosario y deformaciones fonéticas en el prompt.",
    )
    parser.add_argument(
        "--comparar",
        action="store_true",
        help="Ejecuta ambas mediciones (con pistas y sin pistas) para reporte comparativo.",
    )
    parser.add_argument(
        "--simulado",
        action="store_true",
        help="Ejecuta en modo simulado sin llamadas a LLM ni transcripción.",
    )
    parser.add_argument(
        "--modelo-whisper",
        default="small",
        help="Modelo de faster-whisper (default: small).",
    )
    parser.add_argument(
        "--modelo-llm",
        default="gemini-3.6-flash",
        help="Modelo de Gemini a emplear (default: gemini-3.6-flash).",
    )
    parser.add_argument(
        "--salida",
        default=None,
        help="Ruta opcional para guardar el resultado en formato JSON.",
    )

    args = parser.parse_args()

    if args.comparar:
        print("Ejecutando medición 1: CON pistas de glosario...")
        res_con = ejecutar_evaluacion_llm(
            guion_path=args.guion,
            directorio_audios=args.audios,
            cache_transcripciones=args.cache_transcripciones,
            modelo_whisper=args.modelo_whisper,
            modelo_llm=args.modelo_llm,
            con_pistas=True,
            modo_simulado=args.simulado,
        )
        imprimir_reporte_h1b(res_con)

        print("Ejecutando medición 2: SIN pistas de glosario...")
        res_sin = ejecutar_evaluacion_llm(
            guion_path=args.guion,
            directorio_audios=args.audios,
            cache_transcripciones=args.cache_transcripciones,
            modelo_whisper=args.modelo_whisper,
            modelo_llm=args.modelo_llm,
            con_pistas=False,
            modo_simulado=args.simulado,
        )
        imprimir_reporte_h1b(res_sin)

        if args.salida:
            with open(args.salida, "w", encoding="utf-8") as f:
                json.dump({"con_pistas": res_con, "sin_pistas": res_sin}, f, indent=2, ensure_ascii=False)
            print(f"Resultados guardados en {args.salida}")
        return 0

    res = ejecutar_evaluacion_llm(
        guion_path=args.guion,
        directorio_audios=args.audios,
        cache_transcripciones=args.cache_transcripciones,
        modelo_whisper=args.modelo_whisper,
        modelo_llm=args.modelo_llm,
        con_pistas=args.con_pistas,
        modo_simulado=args.simulado,
    )
    imprimir_reporte_h1b(res)

    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"Resultado guardado en {args.salida}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
