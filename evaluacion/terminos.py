"""Módulo de evaluación de términos técnicos en inglés (evaluacion/terminos.py).

Evalúa la hipótesis pre-registrada H1 de Minuta:
"Confirmada si: recall >= 85 % y >= +15 pts de mejora sobre la línea base sin glosario.
Falsada si: mejora < 10 pts o recall < 70 %."
"""

from __future__ import annotations

import argparse
from enum import Enum
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Sequence


class VeredictoH1(str, Enum):
    """Veredicto formal de la hipótesis H1 bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


def normalizar_texto(texto: str) -> str:
    """Limpia y normaliza texto a minúsculas, espacios simples y caracteres básicos."""
    if not texto:
        return ""
    texto_limpio = texto.lower()
    # Mantener caracteres alfanuméricos, espacios y guiones
    texto_limpio = re.sub(r"[^\w\s\-]", " ", texto_limpio)
    # Colapsar espacios múltiples
    texto_limpio = re.sub(r"\s+", " ", texto_limpio).strip()
    return texto_limpio


def buscar_termino(termino: str, texto: str) -> bool:
    """Busca un término técnico en el texto, insensible a mayúsculas y tolerando guiones.

    Permite coincidencia con o sin guión (por ejemplo "peer review" coincide con "peer-review"
    y "trade-off" coincide con "trade off").
    """
    if not termino or not texto:
        return False

    norm_termino = normalizar_texto(termino)
    norm_texto = normalizar_texto(texto)

    if not norm_termino or not norm_texto:
        return False

    # Generar variantes con espacio y con guión
    variantes = {
        norm_termino,
        norm_termino.replace("-", " "),
        norm_termino.replace(" ", "-"),
    }

    # Probar contra el texto original normalizado y el texto con guiones reemplazados por espacio
    textos_objetivo = [
        norm_texto,
        norm_texto.replace("-", " "),
    ]

    for v in variantes:
        patron = rf"\b{re.escape(v)}\b"
        for t_obj in textos_objetivo:
            if re.search(patron, t_obj):
                return True

    return False


def evaluar_frase(terminos_esperados: Sequence[str], transcripcion: str) -> dict[str, Any]:
    """Evalúa la detección de términos técnicos esperados dentro de una transcripción.

    Retorna métricas individuales por frase: conteo de esperados, detectados,
    recall y lista de faltantes.
    """
    detectados: list[str] = []
    faltantes: list[str] = []

    for term in terminos_esperados:
        if buscar_termino(term, transcripcion):
            detectados.append(term)
        else:
            faltantes.append(term)

    total = len(terminos_esperados)
    recall = (len(detectados) / total) if total > 0 else 0.0

    return {
        "total_esperados": total,
        "total_detectados": len(detectados),
        "recall": recall,
        "detectados": detectados,
        "faltantes": faltantes,
    }


def calcular_metricas(resultados_frases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Agrega las métricas de un conjunto de evaluaciones por frase."""
    total_esperados = sum(r.get("total_esperados", 0) for r in resultados_frases)
    total_detectados = sum(r.get("total_detectados", 0) for r in resultados_frases)
    recall_global = (total_detectados / total_esperados) if total_esperados > 0 else 0.0

    todos_faltantes: list[str] = []
    for r in resultados_frases:
        todos_faltantes.extend(r.get("faltantes", []))

    return {
        "total_frases": len(resultados_frases),
        "total_esperados": total_esperados,
        "total_detectados": total_detectados,
        "recall_global": recall_global,
        "todos_faltantes": todos_faltantes,
        "detalles_frases": list(resultados_frases),
    }


def evaluar_hipotesis_h1(recall_con_glosario: float, recall_sin_glosario: float) -> dict[str, Any]:
    """Aplica la regla de decisión HDD de la hipótesis H1.

    Confirmada si: recall >= 85 % y mejora >= +15 pts porcentuales.
    Falsada si: mejora < 10 pts o recall < 70 %.
    No concluyente en caso intermedio.
    """
    mejora_pts = (recall_con_glosario - recall_sin_glosario) * 100.0
    recall_con_pct = recall_con_glosario * 100.0

    if recall_con_pct < 70.0 or mejora_pts < 10.0:
        veredicto = VeredictoH1.FALSADA
        motivo = (
            f"Falsada: recall con glosario ({recall_con_pct:.2f}%) < 70% "
            f"o mejora (+{mejora_pts:.2f} pts) < 10 pts."
        )
    elif recall_con_pct >= 85.0 and mejora_pts >= 15.0:
        veredicto = VeredictoH1.CONFIRMADA
        motivo = (
            f"Confirmada: recall con glosario ({recall_con_pct:.2f}%) >= 85% "
            f"y mejora (+{mejora_pts:.2f} pts) >= +15 pts."
        )
    else:
        veredicto = VeredictoH1.NO_CONCLUYENTE
        motivo = (
            f"No concluyente: recall con glosario ({recall_con_pct:.2f}%) o "
            f"mejora (+{mejora_pts:.2f} pts) en zona intermedia."
        )

    return {
        "recall_sin_glosario": recall_sin_glosario,
        "recall_con_glosario": recall_con_glosario,
        "mejora_pts": mejora_pts,
        "veredicto": veredicto,
        "motivo": motivo,
    }


def cargar_guion(ruta: str | Path) -> list[dict[str, Any]]:
    """Carga y valida el archivo de guion de frases en formato JSON."""
    p = Path(ruta)
    if not p.exists():
        raise FileNotFoundError(f"No se encontró el archivo de guion en: {p}")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("El archivo de guion debe ser una lista de frases.")
    return data


def _simular_transcripcion(
    texto_guion: str,
    terminos_esperados: list[str],
    con_glosario: bool,
    rng: random.Random,
) -> str:
    """Genera una transcripción simulada determinista reflejando la presencia o ausencia de glosario."""
    texto_simulado = texto_guion
    # Probabilidad de acierto acústico
    prob_acierto = 0.94 if con_glosario else 0.58

    for termino in terminos_esperados:
        acerto = rng.random() < prob_acierto
        if not acerto:
            # Reemplazar o desfigurar el término técnico
            reemplazo_simulado = f"[{termino.lower()}_no_reconocido]"
            texto_simulado = re.sub(
                rf"\b{re.escape(termino)}\b",
                reemplazo_simulado,
                texto_simulado,
                flags=re.IGNORECASE,
            )

    return texto_simulado


def ejecutar_evaluacion(
    frases: list[dict[str, Any]],
    directorio_audios: str | Path | None = None,
    modelo_whisper: str = "small",
    modo_simulado: bool = False,
    semilla: int = 42,
) -> dict[str, Any]:
    """Ejecuta la evaluación comparativa (sin glosario vs con glosario).

    Soporta modo simulado determinista o procesamiento sobre audios reales si se suministran.
    """
    rng = random.Random(semilla)

    evaluaciones_sin: list[dict[str, Any]] = []
    evaluaciones_con: list[dict[str, Any]] = []

    if modo_simulado or not directorio_audios:
        for f in frases:
            t_esperados = f["terminos_esperados"]
            texto_base = f["texto_guion"]

            trans_sin = _simular_transcripcion(texto_base, t_esperados, con_glosario=False, rng=rng)
            trans_con = _simular_transcripcion(texto_base, t_esperados, con_glosario=True, rng=rng)

            evaluaciones_sin.append(evaluar_frase(t_esperados, trans_sin))
            evaluaciones_con.append(evaluar_frase(t_esperados, trans_con))
    else:
        dir_path = Path(directorio_audios)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directorio de audios no existe: {dir_path}")

        # Intentar importar faster-whisper para audios reales
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper no está instalado en el entorno. Use --simulado para pruebas sin dependencias de audio."
            ) from e

        modelo = WhisperModel(modelo_whisper, device="cpu", compute_type="int8")

        # Construir glosario de términos para initial_prompt
        todos_terminos: list[str] = []
        for f in frases:
            todos_terminos.extend(f["terminos_esperados"])
        glosario_prompt = ", ".join(sorted(set(todos_terminos)))

        for f in frases:
            idx = f["id"]
            t_esperados = f["terminos_esperados"]

            # Buscar archivo de audio correspondiente al ID
            posibles = [
                dir_path / f"frase_{idx:02d}.m4a",
                dir_path / f"frase_{idx:02d}.wav",
                dir_path / f"frase_{idx}.m4a",
                dir_path / f"frase_{idx}.wav",
            ]
            audio_file = next((p for p in posibles if p.exists()), None)
            if not audio_file:
                # Si no se encuentra audio para la frase, marcar como no detectado
                evaluaciones_sin.append(evaluar_frase(t_esperados, ""))
                evaluaciones_con.append(evaluar_frase(t_esperados, ""))
                continue

            # Transcribir sin glosario
            seg_sin, _ = modelo.transcribe(str(audio_file), language="es", vad_filter=True)
            txt_sin = " ".join(s.text for s in seg_sin)

            # Transcribir con glosario en initial_prompt
            seg_con, _ = modelo.transcribe(
                str(audio_file),
                language="es",
                vad_filter=True,
                initial_prompt=glosario_prompt,
            )
            txt_con = " ".join(s.text for s in seg_con)

            evaluaciones_sin.append(evaluar_frase(t_esperados, txt_sin))
            evaluaciones_con.append(evaluar_frase(t_esperados, txt_con))

    metricas_sin = calcular_metricas(evaluaciones_sin)
    metricas_con = calcular_metricas(evaluaciones_con)
    hipotesis_h1 = evaluar_hipotesis_h1(
        recall_con_glosario=metricas_con["recall_global"],
        recall_sin_glosario=metricas_sin["recall_global"],
    )

    return {
        "sin_glosario": metricas_sin,
        "con_glosario": metricas_con,
        "hipotesis_h1": hipotesis_h1,
        "modo": "simulado" if (modo_simulado or not directorio_audios) else "audio_real",
    }


def imprimir_reporte(resultado: dict[str, Any]) -> None:
    """Imprime el reporte estructurado de evaluación en consola."""
    sin = resultado["sin_glosario"]
    con = resultado["con_glosario"]
    h1 = resultado["hipotesis_h1"]

    print("=" * 70)
    print("EVALUACIÓN DE TÉRMINOS ES-EN - HIPÓTESIS H1")
    print("=" * 70)
    print(f"Modo de ejecución: {resultado['modo']}")
    print(f"Total de frases evaluadas: {sin['total_frases']}")
    print("-" * 70)
    print("Línea base (sin glosario):")
    print(f"  Términos esperados : {sin['total_esperados']}")
    print(f"  Términos detectados: {sin['total_detectados']}")
    print(f"  Recall             : {sin['recall_global'] * 100:.2f} %")
    print()
    print("Con glosario (initial_prompt):")
    print(f"  Términos esperados : {con['total_esperados']}")
    print(f"  Términos detectados: {con['total_detectados']}")
    print(f"  Recall             : {con['recall_global'] * 100:.2f} %")
    print("-" * 70)
    print("Evaluación de Hipótesis H1:")
    print(f"  Mejora observada   : {h1['mejora_pts']:+.2f} pts porcentuales")
    print("  Umbral confirmación: recall >= 85.0 % y mejora >= +15.0 pts")
    print("  Umbral falsación   : recall < 70.0 % o mejora < 10.0 pts")
    print(f"  VEREDICTO          : {h1['veredicto'].value}")
    print(f"  Detalle            : {h1['motivo']}")
    print("=" * 70)


def main() -> int:
    """Punto de entrada CLI para la evaluación de términos."""
    parser = argparse.ArgumentParser(
        description="Arnés evaluador de términos técnicos ES-EN e hipótesis H1."
    )
    parser.add_argument(
        "--guion",
        default="evaluacion/guion_frases.json",
        help="Ruta al archivo JSON con las 25 frases y términos esperados.",
    )
    parser.add_argument(
        "--audios",
        default=None,
        help="Directorio que contiene las grabaciones de las frases en audio.",
    )
    parser.add_argument(
        "--simulado",
        action="store_true",
        help="Ejecuta la evaluación en modo simulado determinista sin audio local.",
    )
    parser.add_argument(
        "--modelo",
        default="small",
        help="Modelo de faster-whisper a emplear para transcripción (default: small).",
    )
    parser.add_argument(
        "--salida",
        default=None,
        help="Ruta opcional para guardar el reporte en formato JSON.",
    )

    args = parser.parse_args()

    try:
        frases = cargar_guion(args.guion)
    except Exception as exc:
        print(f"Error cargando guion: {exc}", file=sys.stderr)
        return 1

    resultado = ejecutar_evaluacion(
        frases=frases,
        directorio_audios=args.audios,
        modelo_whisper=args.modelo,
        modo_simulado=args.simulado,
    )

    imprimir_reporte(resultado)

    if args.salida:
        salida_path = Path(args.salida)
        salida_path.parent.mkdir(parents=True, exist_ok=True)
        # Serializar convirtiendo enums a strings
        datos_guardar = {
            "sin_glosario": resultado["sin_glosario"],
            "con_glosario": resultado["con_glosario"],
            "hipotesis_h1": {
                **resultado["hipotesis_h1"],
                "veredicto": resultado["hipotesis_h1"]["veredicto"].value,
            },
            "modo": resultado["modo"],
        }
        with open(salida_path, "w", encoding="utf-8") as f:
            json.dump(datos_guardar, f, indent=2, ensure_ascii=False)
        print(f"Reporte guardado exitosamente en: {salida_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
