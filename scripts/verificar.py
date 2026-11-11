"""Script de verificación de integridad, seguridad y calidad para Minuta.

Verifica:
1. Carga correcta de módulos e importaciones clave.
2. Ausencia de archivo .env en el índice de Git.
3. Ausencia de archivos de audio en el índice de Git (Regla de privacidad L21).
4. Escaneo de secretos en el historial de Git (git log -p) y en los archivos del árbol.
5. Ejecución completa y exitosa de la suite de pruebas (pytest -q).

Retorna código de salida 0 SI Y SOLO SI todas las verificaciones pasan.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable

# Asegurar que el directorio raíz del repositorio esté en sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Extensiones de audio prohibidas en el índice según regla L21
EXTENSIONES_AUDIO = {".m4a", ".mp3", ".wav", ".ogg", ".webm", ".aac"}

# Patrones de secretos (construidos para evitar auto-coincidencia)
PATRONES_SECRETOS = [
    ("Google API Key", re.compile(r"AI" + r"za[0-9A-Za-z\-_]{35}")),
    ("OpenAI API Key", re.compile(r"sk-" + r"[a-zA-Z0-9]{24,}")),
    ("GitHub Personal Access Token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}")),
    ("Clave privada RSA/EC/SSH", re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----")),
    ("AWS Access Key ID", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    (
        "Asignación de clave genérica sospechosa",
        re.compile(
            r"""(?i)(?:api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['"]([a-zA-Z0-9_\-]{24,})['"]"""
        ),
    ),
]

# Términos que indican un falso positivo o marcador de posición legítimo
FALSOS_POSITIVOS = {
    "dummy",
    "placeholder",
    "example",
    "ejemplo",
    "tu_clave",
    "tu_api_key",
    "fake",
    "test_key",
    "testkey",
    "mock",
    "sample",
    "xxxx",
}


def _es_falso_positivo(cadena: str) -> bool:
    """Determina si una coincidencia es un marcador de posición de documentación."""
    cadena_baja = cadena.lower()
    return any(fp in cadena_baja for fp in FALSOS_POSITIVOS)


def check_importaciones() -> tuple[bool, str]:
    """Verifica que los módulos clave de Minuta carguen sin errores."""
    modulos = [
        "minuta.esquemas",
        "app.streamlit_app",
        "entrenamiento.generar_sinteticos",
        "evaluacion.terminos",
    ]
    errores: list[str] = []
    for mod in modulos:
        try:
            __import__(mod)
        except Exception as err:
            errores.append(f"Fallo al importar '{mod}': {err}")

    if errores:
        return False, "\n  - " + "\n  - ".join(errores)
    return True, f"4 módulos principales cargados correctamente ({', '.join(modulos)})"


def check_env_en_indice() -> tuple[bool, str]:
    """Verifica que el archivo .env no esté rastreado en Git."""
    try:
        resultado = subprocess.run(
            ["git", "ls-files", ".env"],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            check=True,
        )
        archivos = resultado.stdout.strip()
        if archivos:
            return False, f"El archivo .env está rastreado en el índice de Git: {archivos}"
        return True, "El archivo .env no está en el índice de Git"
    except subprocess.CalledProcessError as err:
        return False, f"Error al ejecutar git ls-files: {err}"


def check_audio_en_indice() -> tuple[bool, str]:
    """Verifica que ningún archivo de audio esté en el índice de Git (Regla L21)."""
    try:
        resultado = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            check=True,
        )
        archivos_rastreados = resultado.stdout.splitlines()
        audios_detectados: list[str] = [
            f for f in archivos_rastreados if Path(f).suffix.lower() in EXTENSIONES_AUDIO
        ]

        if audios_detectados:
            return (
                False,
                f"Archivos de audio prohibidos encontrados en el índice:\n  - "
                + "\n  - ".join(audios_detectados),
            )
        return True, f"Ningún archivo de audio ({', '.join(sorted(EXTENSIONES_AUDIO))}) en el índice de Git"
    except subprocess.CalledProcessError as err:
        return False, f"Error al consultar el índice de Git: {err}"


def check_secretos() -> tuple[bool, str]:
    """Verifica ausencia de secretos en git log -p y en archivos del árbol de trabajo."""
    hallazgos: list[str] = []

    # 1. Escaneo de git log -p
    try:
        resultado_log = subprocess.run(
            ["git", "log", "-p", "-n", "100"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ROOT_DIR,
            check=True,
        )
        diff_total = resultado_log.stdout

        for nombre_patron, regex in PATRONES_SECRETOS:
            for match in regex.finditer(diff_total):
                texto_coincidente = match.group(0)
                if not _es_falso_positivo(texto_coincidente):
                    # Verificar si la coincidencia proviene de la definición de scripts/verificar.py
                    fragmento = diff_total[max(0, match.start() - 40) : min(len(diff_total), match.end() + 40)]
                    if "scripts/verificar.py" in fragmento:
                        continue
                    hallazgos.append(
                        f"Posible secreto en git log ({nombre_patron}): {texto_coincidente[:12]}..."
                    )
    except subprocess.CalledProcessError as err:
        return False, f"Error al ejecutar git log -p: {err}"

    # 2. Escaneo de archivos del árbol (rastreados + no ignorados)
    try:
        res_archivos = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            check=True,
        )
        archivos_revisar = res_archivos.stdout.splitlines()

        for rel_path in archivos_revisar:
            # Omitir el propio verificador y binarios
            if rel_path == "scripts/verificar.py" or rel_path.endswith((".png", ".jpg", ".pdf", ".ico")):
                continue
            ruta_completa = ROOT_DIR / rel_path
            if not ruta_completa.is_file():
                continue

            try:
                contenido = ruta_completa.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for nombre_patron, regex in PATRONES_SECRETOS:
                for match in regex.finditer(contenido):
                    texto_coincidente = match.group(0)
                    if not _es_falso_positivo(texto_coincidente):
                        hallazgos.append(
                            f"Posible secreto en {rel_path} ({nombre_patron}): {texto_coincidente[:12]}..."
                        )
    except subprocess.CalledProcessError as err:
        return False, f"Error al listar archivos para escaneo: {err}"

    if hallazgos:
        return False, "Secretos o credenciales detectadas:\n  - " + "\n  - ".join(hallazgos)
    return True, "No se detectaron secretos ni credenciales en el historial ni en el árbol"


def check_pytest() -> tuple[bool, str]:
    """Ejecuta la suite completa de pruebas unitarias y e2e con pytest -q."""
    try:
        env_cmd = os.environ.copy()
        env_cmd["PYTHONPATH"] = str(ROOT_DIR)
        resultado = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            env=env_cmd,
        )
        if resultado.returncode != 0:
            salida = resultado.stdout.strip() or resultado.stderr.strip()
            return False, f"pytest finalizó con código {resultado.returncode}:\n{salida}"

        resumen = resultado.stdout.strip().splitlines()[-1] if resultado.stdout.strip() else "OK"
        return True, f"Suite de pytest en verde ({resumen})"
    except Exception as err:
        return False, f"Error al ejecutar pytest: {err}"


def main() -> None:
    """Ejecuta todas las verificaciones y emite el código de salida adecuado."""
    print("=" * 70)
    print("  VERIFICACIÓN DE INTEGRIDAD, SEGURIDAD Y CALIDAD: MINUTA")
    print("=" * 70)

    verificaciones: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
        ("Módulos e importaciones principales", check_importaciones),
        ("Exclusión de .env en el índice de Git", check_env_en_indice),
        ("Exclusión de audios en el índice de Git (L21)", check_audio_en_indice),
        ("Escaneo de secretos (git log -p y árbol)", check_secretos),
        ("Suite de pruebas completa (pytest -q)", check_pytest),
    ]

    todos_pasaron = True
    for nombre, fn_check in verificaciones:
        ok, detalle = fn_check()
        simbolo = "[OK]  " if ok else "[FAIL]"
        print(f"\n{simbolo} {nombre}")
        print(f"       -> {detalle}")
        if not ok:
            todos_pasaron = False

    print("\n" + "=" * 70)
    if todos_pasaron:
        print("  RESULTADO: TODAS LAS COMPROBACIONES PASARON CON ÉXITO (CÓDIGO 0)")
        print("=" * 70)
        sys.exit(0)
    else:
        print("  RESULTADO: FALLARON UNA O MÁS COMPROBACIONES (CÓDIGO 1)")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
