"""Pruebas unitarias para minuta/glosario.py.

Verifica el glosario de investigación predeterminado, la normalización
de términos adicionales y el formateo/recorte acotado de hotwords para faster-whisper.
"""

from __future__ import annotations

import warnings
import pytest

from minuta.glosario import (
    estimar_tokens,
    formatear_hotwords,
    normalizar_glosario,
    obtener_glosario_defecto,
)


def test_obtener_glosario_defecto_contiene_terminos_clave():
    """Verifica que el glosario por defecto contenga los términos académicos requeridos."""
    glosario = obtener_glosario_defecto()
    assert isinstance(glosario, list)
    assert len(glosario) >= 30

    terminos_esperados = [
        "peer review",
        "preprint",
        "dataset",
        "benchmark",
        "paper",
        "journal",
        "grant",
        "draft",
        "literature review",
        "baseline",
        "state of the art",
        "open access",
        "trade-off",
        "ablation study",
        "call for papers",
        "camera-ready",
        "citation count",
        "h-index",
        "submission",
        "workshop",
        "conference proceedings",
        "survey",
        "feedback",
        "pipeline",
        "framework",
        "panel data",
        "p-value",
        "clustering",
        "overfitting",
        "web scraping",
        "ETL",
        "LLM",
        "embeddings",
    ]

    glosario_lower = [t.lower() for t in glosario]
    for term in terminos_esperados:
        assert term.lower() in glosario_lower, f"Término requerido '{term}' ausente en glosario por defecto"


def test_normalizar_glosario_sin_adicionales():
    """Verifica que sin términos adicionales devuelva el glosario por defecto ordenado."""
    resultado = normalizar_glosario()
    assert len(resultado) == len(obtener_glosario_defecto())
    assert resultado == sorted(resultado, key=lambda s: s.lower())


def test_normalizar_glosario_con_adicionales_y_limpieza():
    """Verifica unión, limpieza de espacios, eliminación de vacíos y deduplicación."""
    adicionales = [
        "  Machine Learning  ",
        "paper",  # ya existe en el por defecto
        "   ",    # vacío
        "deep learning",
        "PAPER",  # duplicado insensible a mayúsculas
    ]

    resultado = normalizar_glosario(adicionales)
    resultado_lower = [t.lower() for t in resultado]

    assert "machine learning" in resultado_lower
    assert "deep learning" in resultado_lower
    # "paper" no debe estar duplicado
    assert resultado_lower.count("paper") == 1
    # no debe haber cadenas vacías
    assert "" not in resultado
    # debe estar ordenado alfabéticamente
    assert resultado == sorted(resultado, key=lambda s: s.lower())


def test_formatear_hotwords_dentro_del_limite():
    """Verifica el formateo para una lista pequeña que cabe dentro de max_tokens."""
    terminos = ["peer review", "preprint", "dataset", "benchmark"]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        hotwords = formatear_hotwords(terminos, max_tokens=220)
        assert len(w) == 0

    assert hotwords == "peer review preprint dataset benchmark"
    assert estimar_tokens(hotwords) <= 220


def test_formatear_hotwords_vacio():
    """Verifica que una lista vacía devuelva cadena vacía sin emitir advertencia."""
    hotwords = formatear_hotwords([], max_tokens=220)
    assert hotwords == ""


def test_formatear_hotwords_excedente_emite_advertencia_y_recorta():
    """Verifica que una lista extensa (>220 tokens) sea recortada y emita UserWarning."""
    # Creamos una lista extensa de ~100 términos largos
    terminos_largos = [f"termino_academico_muy_largo_numero_{i:03d}" for i in range(120)]

    with pytest.warns(UserWarning, match=r"Se recortaron \d+ términos"):
        hotwords = formatear_hotwords(terminos_largos, max_tokens=220)

    assert hotwords != ""
    assert estimar_tokens(hotwords) <= 220
    # Comprobar que no están todos los 120 términos incluidos
    tokens_incluidos = hotwords.split()
    assert len(tokens_incluidos) < 120
