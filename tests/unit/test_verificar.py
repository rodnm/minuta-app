"""Pruebas unitarias para scripts/verificar.py y reglas de privacidad (T60)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

from scripts.verificar import EXTENSIONES_AUDIO, ROOT_DIR, check_audio_en_indice, check_secretos

EXTENSIONES_ESPERADAS = {
    ".flac",
    ".opus",
    ".3gp",
    ".amr",
    ".aac",
    ".ogg",
    ".webm",
    ".m4a",
    ".mp3",
    ".wav",
}


def test_extensiones_audio_completas():
    """T60: Verifica que EXTENSIONES_AUDIO contenga las 10 extensiones requeridas."""
    assert EXTENSIONES_ESPERADAS.issubset(EXTENSIONES_AUDIO)


def test_gitignore_ignora_todas_las_extensiones_de_audio(tmp_path):
    """T60: Verifica que git ignore cada una de las 10 extensiones de audio en cualquier ruta."""
    for ext in EXTENSIONES_ESPERADAS:
        archivo_simulado = ROOT_DIR / "tests" / f"audio_prueba{ext}"
        # Usar git check-ignore para validar que la regla de gitignore aplica
        res = subprocess.run(
            ["git", "check-ignore", "-q", str(archivo_simulado)],
            cwd=ROOT_DIR,
        )
        assert res.returncode == 0, f"La extensión {ext} no está ignorada por git ({archivo_simulado})"


def test_verificar_no_imprime_fragmento_de_secreto(monkeypatch, tmp_path):
    """T60: verificar.py no debe filtrar ningún fragmento del secreto detectado."""
    # Creamos un archivo temporal dentro del repo con un patrón de API key realístico (sin falsos positivos)
    # Patrón Google API Key: AIza + 35 caracteres = 39 caracteres
    falso_secreto = "AIzaSy" + "B41982739182371928371982739812733"
    assert len(falso_secreto) == 39
    archivo_prueba = ROOT_DIR / "tests" / "unit" / "_temp_secreto_test.txt"
    try:
        archivo_prueba.write_text(f"api_key = '{falso_secreto}'\n", encoding="utf-8")
        # Forzamos a git ls-files a incluir este archivo
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda cmd, **kwargs: (
                subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout="tests/unit/_temp_secreto_test.txt\n",
                    stderr="",
                )
                if "ls-files" in cmd
                else subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            ),
        )
        pasa, msg = check_secretos()
        assert not pasa, "Debió detectar el secreto sospechoso"
        # Asegurar que NINGÚN fragmento (de 4 o más caracteres) del secreto aparezca en el mensaje
        for i in range(len(falso_secreto) - 4):
            fragmento = falso_secreto[i : i + 5]
            assert fragmento not in msg, f"Se filtró fragmento '{fragmento}' en el mensaje: {msg}"
    finally:
        if archivo_prueba.exists():
            archivo_prueba.unlink()
