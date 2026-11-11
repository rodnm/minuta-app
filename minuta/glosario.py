"""Módulo de glosario de investigación y gestión de hotwords (minuta/glosario.py).

Provee un glosario de investigación en español/inglés predeterminado para guiar
la transcripción acústica en faster-whisper mediante el parámetro hotwords,
así como funciones para normalizar términos adicionales del usuario y acotar
la longitud para no saturar la ventana de atención (220 tokens).

ESTRICTAMENTE PROHIBIDO importar nada desde evaluacion/.
"""

from __future__ import annotations

import math
import warnings

# Glosario general de investigación científica y tecnológica (ES/EN)
# Fijado a priori con términos estándar de la literatura y práctica académica.
_GLOSARIO_INVESTIGACION_DEFECTO: tuple[str, ...] = (
    "ablation study",
    "baseline",
    "benchmark",
    "call for papers",
    "camera-ready",
    "citation count",
    "clustering",
    "conference proceedings",
    "cross-validation",
    "data augmentation",
    "dataset",
    "deep learning",
    "draft",
    "embeddings",
    "ETL",
    "feedback",
    "fine-tuning",
    "framework",
    "grant",
    "ground truth",
    "h-index",
    "journal",
    "literature review",
    "LLM",
    "machine learning",
    "neural network",
    "open access",
    "overfitting",
    "p-value",
    "panel data",
    "paper",
    "peer review",
    "pipeline",
    "preprint",
    "prompt engineering",
    "state of the art",
    "submission",
    "survey",
    "trade-off",
    "transfer learning",
    "transformer",
    "web scraping",
    "workshop",
    "zero-shot",
)


def obtener_glosario_defecto() -> list[str]:
    """Retorna una copia de la lista de términos de investigación predeterminados."""
    return list(_GLOSARIO_INVESTIGACION_DEFECTO)


def normalizar_glosario(terminos_adicionales: list[str] | None = None) -> list[str]:
    """Une el glosario por defecto con términos adicionales provistos por el usuario.

    Limpia espacios en blanco, descarta entradas vacías, elimina duplicados de forma
    insensible a mayúsculas/minúsculas y devuelve la lista ordenada alfabéticamente.
    """
    todos: list[str] = list(_GLOSARIO_INVESTIGACION_DEFECTO)
    if terminos_adicionales:
        todos.extend(terminos_adicionales)

    vistos: set[str] = set()
    resultado: list[str] = []

    for t in todos:
        limpio = t.strip()
        if not limpio:
            continue
        clave = limpio.lower()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(limpio)

    resultado.sort(key=lambda s: s.lower())
    return resultado


def estimar_tokens(texto: str) -> int:
    """Estima la cantidad de tokens BPE de un texto.

    Aproximación estándar para Whisper (1 token ~ 3.7 caracteres o ~1.3 tokens por palabra).
    """
    if not texto.strip():
        return 0
    tokens_chars = len(texto) / 3.7
    tokens_words = len(texto.split()) * 1.3
    return max(1, math.ceil(max(tokens_chars, tokens_words)))


def formatear_hotwords(glosario: list[str], max_tokens: int = 220) -> str:
    """Formatea la lista de términos para el parámetro hotwords de faster-whisper.

    faster-whisper inyecta hotwords en cada ventana de 30 s de decodificación.
    Si la lista acumulada supera la cota de max_tokens (~220 tokens o ~800 caracteres),
    recorta los términos excedentes y emite una advertencia UserWarning indicando
    la cantidad de términos excluidos.
    """
    if not glosario:
        return ""

    terminos_incluidos: list[str] = []
    terminos_recortados = 0

    for i, termino in enumerate(glosario):
        limpio = termino.strip()
        if not limpio:
            continue

        candidato = " ".join(terminos_incluidos + [limpio]) if terminos_incluidos else limpio
        tokens = estimar_tokens(candidato)

        if tokens <= max_tokens:
            terminos_incluidos.append(limpio)
        else:
            terminos_recortados = len(glosario) - i
            break

    if terminos_recortados > 0:
        warnings.warn(
            f"Se recortaron {terminos_recortados} términos del glosario para no exceder la cota de {max_tokens} tokens.",
            UserWarning,
            stacklevel=2,
        )

    return " ".join(terminos_incluidos)
