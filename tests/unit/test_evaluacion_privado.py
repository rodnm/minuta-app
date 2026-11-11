"""Pruebas unitarias para evaluacion/privado.py (Caja negra de privacidad T61)."""

from __future__ import annotations

import io
import json
from pathlib import Path
import pytest

from minuta.esquemas import Segmento, Transcripcion


def test_import_privado():
    """T61: Verifica que evaluacion.privado exista y sea importable."""
    from evaluacion import privado
    assert hasattr(privado, "procesar_privado") or hasattr(privado, "ejecutar_caja_negra")


def test_caja_negra_no_imprime_palabras_de_transcrito(tmp_path, monkeypatch, capsys):
    """T61: La caja negra nunca debe imprimir ninguna palabra del contenido transcrito."""
    from evaluacion.privado import procesar_privado

    palabras_secretas = [
        "termino_ultrasecreto_alpha",
        "confidencial_beta_99",
        "salario_secreto_gamma",
        "proyecto_omega_x",
    ]
    texto_privado = " ".join(palabras_secretas)

    transcripcion_falsa = Transcripcion(
        audio_id="falso_audio",
        duracion_s=120.0,
        idioma="es",
        modelo="small",
        segmentos=[
            Segmento(id=1, inicio_s=0.0, fin_s=30.0, texto=texto_privado),
            Segmento(id=2, inicio_s=30.0, fin_s=60.0, texto="otra frase de relleno confidencial"),
        ],
    )

    salidas_dir = tmp_path / "salidas"

    # Ejecutar procesamiento con mock de LLM y sin llamadas reales
    metricas = procesar_privado(
        transcripcion=transcripcion_falsa,
        salidas_dir=salidas_dir,
        tipo_plantilla="reunion",
        proveedor_simulado=True,
    )

    captured = capsys.readouterr()
    salida_completa = (captured.out + "\n" + captured.err).lower()

    # Ninguna palabra secreta del audio debe aparecer en stdout o stderr
    for palabra in palabras_secretas:
        assert palabra.lower() not in salida_completa, f"Fuga de texto privado detectada: '{palabra}' en salida."

    # Debe retornar métricas agregadas (números)
    assert "duracion_s" in metricas
    assert metricas["duracion_s"] == 120.0
    assert (salidas_dir / "transcripcion.json").exists()


def test_caja_negra_errores_sin_contenido(tmp_path, capsys):
    """T61: Los mensajes de error nunca deben incluir fragmentos de texto del contenido."""
    from evaluacion.privado import reportar_error_anonimo

    # Simular un error con un texto que contenía información confidencial
    error_con_secreto = ValueError("Fallo en bloque 1: no se pudo parsear 'termino_ultrasecreto_alpha'")
    msg = reportar_error_anonimo("bloque 1", error_con_secreto)

    assert "termino_ultrasecreto_alpha" not in msg
    assert "bloque 1" in msg


def test_caja_negra_cli_sin_audio(monkeypatch, capsys):
    """T61: CLI sin argumentos reporta error anónimo y código distinto de cero."""
    import sys
    from evaluacion.privado import main

    monkeypatch.setattr(sys, "argv", ["privado.py"])
    rc = main()
    assert rc == 2
    captured = capsys.readouterr()
    assert "argumentos" in captured.err
