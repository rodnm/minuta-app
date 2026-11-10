"""Pruebas unitarias para el arnés de evaluación de términos (evaluacion/terminos.py).

Cubre la verificación del guion de 25 frases ES-EN, normalización y búsqueda
de términos técnicos en inglés, cálculo de métricas (recall, precisión),
lógica de decisión de la hipótesis H1 y ejecución en modo simulado.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluacion.terminos import (
    buscar_termino,
    calcular_metricas,
    cargar_guion,
    evaluar_frase,
    evaluar_hipotesis_h1,
    ejecutar_evaluacion,
    main as terminos_main,
    normalizar_texto,
    validar_escritura_resultados,
    VeredictoH1,
)


RUTA_GUION = Path(__file__).resolve().parents[2] / "evaluacion" / "guion_frases.json"


def test_guion_formato_e_integridad() -> None:
    """Valida que el archivo de guion exista, tenga 25 frases y respete el esquema."""
    assert RUTA_GUION.exists(), f"El archivo {RUTA_GUION} no existe."

    with open(RUTA_GUION, encoding="utf-8") as f:
        frases = json.load(f)

    assert isinstance(frases, list), "El contenido raíz debe ser una lista."
    assert len(frases) == 25, f"Se esperaban exactamente 25 frases, se hallaron {len(frases)}."

    ids_vistos = set()
    for item in frases:
        assert "id" in item, "Cada elemento debe contener la clave 'id'."
        assert "texto_guion" in item, "Cada elemento debe contener 'texto_guion'."
        assert "terminos_esperados" in item, "Cada elemento debe contener 'terminos_esperados'."

        idx = item["id"]
        assert isinstance(idx, int), f"El id {idx} debe ser entero."
        assert 1 <= idx <= 25, f"El id {idx} está fuera del rango 1-25."
        ids_vistos.add(idx)

        texto = item["texto_guion"]
        assert isinstance(texto, str) and len(texto.strip()) > 10, "El texto del guion es inválido."

        terminos = item["terminos_esperados"]
        assert isinstance(terminos, list) and len(terminos) >= 1, "Debe haber al menos un término esperado."
        for term in terminos:
            assert isinstance(term, str) and len(term.strip()) > 0, "Cada término debe ser texto no vacío."

        # Regla L25 y anonimato
        texto_bajo = texto.lower()
        assert "yorno" not in texto_bajo, "Regla L25: No incluir 'yorno'."
        assert "encupus" not in texto_bajo, "Regla L25: No incluir 'encupus'."
        assert "centrum" not in texto_bajo, "Anonimato: no nombrar instituciones de empleadores."
        assert "pucp" not in texto_bajo, "Anonimato: no nombrar instituciones de empleadores."

    assert len(ids_vistos) == 25, "Los IDs deben ser únicos del 1 al 25."


def test_normalizar_texto() -> None:
    """Verifica normalización de texto eliminando puntuación extrema y espacios extra."""
    ejemplo = "  ¡Tenemos que enviar el Paper al Journal, pronto!  "
    normalizado = normalizar_texto(ejemplo)
    assert normalizado == "tenemos que enviar el paper al journal pronto"


def test_buscar_termino_exacto_y_variaciones() -> None:
    """Verifica búsqueda insensible a mayúsculas y tolerante a guiones o espacios."""
    texto = "el proceso de peer review requirió un trade-off según los reviewers"

    assert buscar_termino("peer review", texto) is True
    assert buscar_termino("peer-review", texto) is True
    assert buscar_termino("trade-off", texto) is True
    assert buscar_termino("trade off", texto) is True
    assert buscar_termino("reviewers", texto) is True
    assert buscar_termino("Scopus", texto) is False


def test_evaluar_frase_aciertos_y_faltantes() -> None:
    """Verifica el desglose de términos detectados y faltantes por frase."""
    terminos = ["paper", "journal", "deadline"]

    # Caso acierto total
    res_total = evaluar_frase(terminos, "enviamos el paper al journal antes del deadline")
    assert res_total["total_esperados"] == 3
    assert res_total["total_detectados"] == 3
    assert res_total["recall"] == 1.0
    assert res_total["faltantes"] == []

    # Caso parcial
    res_parcial = evaluar_frase(terminos, "enviamos el paper al editor antes de tiempo")
    assert res_parcial["total_esperados"] == 3
    assert res_parcial["total_detectados"] == 1
    assert pytest.approx(res_parcial["recall"], 0.01) == 0.333
    assert "journal" in res_parcial["faltantes"]
    assert "deadline" in res_parcial["faltantes"]

    # Caso cero aciertos
    res_cero = evaluar_frase(terminos, "no hay nada en este texto")
    assert res_cero["total_detectados"] == 0
    assert res_cero["recall"] == 0.0
    assert len(res_cero["faltantes"]) == 3


def test_calcular_metricas_globales() -> None:
    """Verifica agregación de métricas globales de evaluación."""
    evaluaciones = [
        {"total_esperados": 2, "total_detectados": 2, "faltantes": []},
        {"total_esperados": 2, "total_detectados": 1, "faltantes": ["journal"]},
        {"total_esperados": 1, "total_detectados": 0, "faltantes": ["grant"]},
    ]
    metricas = calcular_metricas(evaluaciones)
    assert metricas["total_esperados"] == 5
    assert metricas["total_detectados"] == 3
    assert pytest.approx(metricas["recall_global"], 0.01) == 0.60
    assert len(metricas["todos_faltantes"]) == 2


def test_evaluar_hipotesis_h1_criterios() -> None:
    """Evalúa los umbrales pre-registrados de H1:

    Confirmada si: recall >= 85 % y mejora >= +15 pts.
    Falsada si: mejora < 10 pts o recall < 70 %.
    No concluyente en rango intermedio.
    """
    # Caso confirmada: recall con glosario 90 %, sin glosario 65 % (mejora +25 pts)
    res_conf = evaluar_hipotesis_h1(recall_con_glosario=0.90, recall_sin_glosario=0.65)
    assert res_conf["veredicto"] == VeredictoH1.CONFIRMADA
    assert res_conf["mejora_pts"] == pytest.approx(25.0)

    # Caso falsada por mejora < 10 pts (aunque recall_con sea alto)
    res_fal_mejora = evaluar_hipotesis_h1(recall_con_glosario=0.86, recall_sin_glosario=0.80)
    assert res_fal_mejora["veredicto"] == VeredictoH1.FALSADA
    assert res_fal_mejora["mejora_pts"] == pytest.approx(6.0)

    # Caso falsada por recall con glosario < 70 % (aunque mejora sea > 15 pts)
    res_fal_recall = evaluar_hipotesis_h1(recall_con_glosario=0.68, recall_sin_glosario=0.45)
    assert res_fal_recall["veredicto"] == VeredictoH1.FALSADA

    # Caso no concluyente: recall 80 % (>= 70 pero < 85) con mejora 12 pts (>= 10 pero < 15)
    res_no_concl = evaluar_hipotesis_h1(recall_con_glosario=0.80, recall_sin_glosario=0.68)
    assert res_no_concl["veredicto"] == VeredictoH1.NO_CONCLUYENTE


def test_ejecutar_evaluacion_simulada_determinista() -> None:
    """Verifica que el modo simulado corra determinísticamente sobre las 25 frases."""
    frases = cargar_guion(RUTA_GUION)
    resultado = ejecutar_evaluacion(frases, modo_simulado=True, semilla=42)

    assert "sin_glosario" in resultado
    assert "con_glosario" in resultado
    assert "hipotesis_h1" in resultado

    res_sin = resultado["sin_glosario"]
    res_con = resultado["con_glosario"]
    h1 = resultado["hipotesis_h1"]

    assert res_con["recall_global"] > res_sin["recall_global"]
    assert h1["veredicto"] in (VeredictoH1.CONFIRMADA, VeredictoH1.FALSADA, VeredictoH1.NO_CONCLUYENTE)

    # Repetir con la misma semilla debe dar idéntico resultado
    resultado2 = ejecutar_evaluacion(frases, modo_simulado=True, semilla=42)
    assert resultado["hipotesis_h1"]["mejora_pts"] == resultado2["hipotesis_h1"]["mejora_pts"]
    assert resultado["con_glosario"]["recall_global"] == resultado2["con_glosario"]["recall_global"]


def test_cli_modo_simulado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica que el punto de entrada CLI funcione correctamente en modo --simulado."""
    salida_json = tmp_path / "reporte_h1.json"
    args = [
        "terminos.py",
        "--guion",
        str(RUTA_GUION),
        "--simulado",
        "--salida",
        str(salida_json),
    ]
    monkeypatch.setattr(sys, "argv", args)

    codigo_salida = terminos_main()
    assert codigo_salida == 0

    captured = capsys.readouterr()
    assert "EVALUACIÓN DE TÉRMINOS ES-EN - HIPÓTESIS H1" in captured.out
    assert "VEREDICTO" in captured.out
    assert salida_json.exists(), "Debe haberse generado el archivo JSON de salida."

    with open(salida_json, encoding="utf-8") as f:
        datos = json.load(f)
    assert "sin_glosario" in datos
    assert "con_glosario" in datos
    assert "hipotesis_h1" in datos


def test_modo_simulado_imprime_aviso_no_medicion(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifica que el modo simulado imprima explícitamente el aviso de no medición."""
    args = ["terminos.py", "--guion", str(RUTA_GUION), "--simulado"]
    monkeypatch.setattr(sys, "argv", args)
    codigo = terminos_main()
    assert codigo == 0
    captured = capsys.readouterr()
    assert "SIMULADO: no es una medición" in captured.out


def test_modo_simulado_prohibe_escribir_resultados_md(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifica que el modo simulado tenga prohibido escribir en docs/resultados.md."""
    with pytest.raises(PermissionError):
        validar_escritura_resultados("docs/resultados.md", modo_simulado=True)

    with pytest.raises(PermissionError):
        validar_escritura_resultados(Path("docs/resultados.md"), modo_simulado=True)

    # En modo no simulado (audio real), no debe arrojar excepción
    validar_escritura_resultados("docs/resultados.md", modo_simulado=False)

    # A través de CLI en modo simulado debe salir con código 1
    args = [
        "terminos.py",
        "--guion",
        str(RUTA_GUION),
        "--simulado",
        "--salida",
        "docs/resultados.md",
    ]
    monkeypatch.setattr(sys, "argv", args)
    codigo = terminos_main()
    assert codigo == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.err


def test_cli_opciones_glosario_y_metodo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifica que el CLI acepte las opciones --tipo-glosario y --metodo-inyeccion."""
    salida_json = tmp_path / "test_opts.json"
    args = [
        "terminos.py",
        "--guion",
        str(RUTA_GUION),
        "--simulado",
        "--tipo-glosario",
        "producto",
        "--metodo-inyeccion",
        "hotwords",
        "--salida",
        str(salida_json),
    ]
    monkeypatch.setattr(sys, "argv", args)
    codigo = terminos_main()
    assert codigo == 0

    with open(salida_json, encoding="utf-8") as f:
        datos = json.load(f)
    assert datos.get("tipo_glosario") == "producto"
    assert datos.get("metodo_inyeccion") == "hotwords"


def test_cli_clip_5min_requiere_audios(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verifica que --clip-5min aborte con error si no se pasa --audios."""
    args = [
        "terminos.py",
        "--guion",
        str(RUTA_GUION),
        "--clip-5min",
    ]
    monkeypatch.setattr(sys, "argv", args)
    codigo = terminos_main()
    assert codigo == 1
    captured = capsys.readouterr()
    assert "ERROR: --clip-5min requiere especificar el directorio de audios con --audios" in captured.err



