"""Pruebas unitarias para el detector de fugas G4 (evaluacion/privado.py, T62)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import pytest

from evaluacion.privado import ROOT_DIR, extraer_shingles_de_texto, verificar_fugas


def test_extraer_shingles_tamano_8():
    """T62: Verifica que extraer_shingles_de_texto arme n-gramas exactos de 8 palabras."""
    texto = "uno dos tres cuatro cinco seis siete ocho nueve diez"
    shingles = extraer_shingles_de_texto(texto, tamano=8)
    assert len(shingles) == 3
    assert ("uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho") in shingles
    assert ("dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve") in shingles
    assert ("tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez") in shingles


def test_verificar_fugas_repo_limpio():
    """T62: Con el repositorio limpio no debe haber ninguna fuga (coincidencias: 0)."""
    coincidencias = verificar_fugas()
    assert coincidencias == 0


def test_verificar_fugas_detecta_coincidencia(tmp_path, monkeypatch):
    """T62: Si se inserta una frase del transcrito privado en un archivo versionado, detecta coincidencias >= 1."""
    # 1. Crear carpeta privada temporal con una transcripción
    dir_privado = tmp_path / "privado_test"
    dir_privado.mkdir(parents=True)
    frase_secreta = "esta es una discusion estrictamente confidencial de la junta directiva de hoy"
    trans_data = {
        "audio_id": "test_audio",
        "duracion_s": 60.0,
        "segmentos": [{"id": 1, "inicio_s": 0.0, "fin_s": 10.0, "texto": frase_secreta}],
    }
    (dir_privado / "salida_privada.json").write_text(json.dumps(trans_data), encoding="utf-8")

    # 2. Simular archivo en el repo que tiene la misma frase
    archivo_repo = ROOT_DIR / "tests" / "unit" / "_temp_fuga_simulada.txt"
    try:
        archivo_repo.write_text(f"Reporte con fuga: {frase_secreta}\n", encoding="utf-8")

        # Mockear git ls-files para que incluya este archivo
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda cmd, **kwargs: (
                subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout="tests/unit/_temp_fuga_simulada.txt\n",
                    stderr="",
                )
                if "ls-files" in cmd
                else subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            ),
        )

        coincidencias = verificar_fugas(dir_privado=dir_privado)
        assert coincidencias >= 1, f"Debió detectar al menos 1 shingle coincidente, obtuvo {coincidencias}"
    finally:
        if archivo_repo.exists():
            archivo_repo.unlink()


def test_cli_verificar_fugas_salida():
    """T62: Verifica que 'python -m evaluacion.privado --verificar-fugas' imprima 'coincidencias: 0'."""
    res = subprocess.run(
        ["python", "-m", "evaluacion.privado", "--verificar-fugas"],
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
    )
    assert res.returncode == 0
    lineas = res.stdout.strip().splitlines()
    assert any("coincidencias: 0" in l for l in lineas), f"Salida inesperada: {res.stdout}"
