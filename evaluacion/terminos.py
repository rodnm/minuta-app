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
    tipo_glosario: str = "producto",
    metodo_inyeccion: str = "hotwords",
) -> dict[str, Any]:
    """Ejecuta la evaluación comparativa (sin glosario vs con glosario).

    Soporta modo simulado determinista o procesamiento sobre audios reales si se suministran.
    Permite tipo_glosario='producto' (fijado a priori) o 'filtrado', y metodo_inyeccion='hotwords' o 'initial_prompt'.
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
            from evaluacion.velocidad import _aplicar_parches_compatibilidad, obtener_directorio_cache
            _aplicar_parches_compatibilidad()
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper no está instalado en el entorno. Use --simulado para pruebas sin dependencias de audio."
            ) from e

        dir_cache = obtener_directorio_cache()
        modelo = WhisperModel(
            modelo_whisper,
            device="cpu",
            compute_type="int8",
            download_root=dir_cache,
        )

        # Construir glosario según tipo seleccionado
        if tipo_glosario == "producto":
            from minuta.glosario import obtener_glosario_defecto, formatear_hotwords
            glosario_lista = obtener_glosario_defecto()
            glosario_hotwords = formatear_hotwords(glosario_lista)
            glosario_prompt = ", ".join(glosario_lista)
        else:
            todos_terminos: list[str] = []
            for f in frases:
                todos_terminos.extend(f["terminos_esperados"])
            glosario_prompt = ", ".join(sorted(set(todos_terminos)))
            glosario_hotwords = glosario_prompt

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

            # Transcribir sin glosario (línea base)
            seg_sin, _ = modelo.transcribe(str(audio_file), language="es", vad_filter=True)
            txt_sin = " ".join(s.text for s in seg_sin)

            # Transcribir con glosario según método de inyección
            if metodo_inyeccion == "hotwords":
                seg_con, _ = modelo.transcribe(
                    str(audio_file),
                    language="es",
                    vad_filter=True,
                    hotwords=glosario_hotwords,
                )
            else:
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
        "tipo_glosario": tipo_glosario,
        "metodo_inyeccion": metodo_inyeccion,
    }


def evaluar_clip_5min(
    directorio_audios: str | Path,
    frases: Sequence[dict[str, Any]],
    modelo_whisper: str = "small",
    duracion_s: float = 300.0,
    tipo_glosario: str = "producto",
) -> dict[str, Any]:
    """Evalúa la transcripción continua de ~5 min concatenada en memoria RAM.

    Compara línea base (sin glosario) vs initial_prompt vs hotwords sobre el total de términos esperados.
    """
    from evaluacion.velocidad import _aplicar_parches_compatibilidad, obtener_directorio_cache, cargar_y_concatenar_audios
    _aplicar_parches_compatibilidad()
    from faster_whisper import WhisperModel

    audio_array = cargar_y_concatenar_audios(directorio_audios, duracion_objetivo_s=duracion_s)

    if tipo_glosario == "producto":
        from minuta.glosario import obtener_glosario_defecto, formatear_hotwords
        glosario_lista = obtener_glosario_defecto()
        glosario_hotwords = formatear_hotwords(glosario_lista)
        glosario_prompt = ", ".join(glosario_lista)
    else:
        todos = []
        for f in frases:
            todos.extend(f["terminos_esperados"])
        glosario_prompt = ", ".join(sorted(set(todos)))
        glosario_hotwords = glosario_prompt

    todos_terminos: list[str] = []
    for f in frases:
        todos_terminos.extend(f["terminos_esperados"])

    dir_cache = obtener_directorio_cache()
    modelo = WhisperModel(modelo_whisper, device="cpu", compute_type="int8", download_root=dir_cache)

    # 1. Base (sin glosario)
    segs_base, _ = modelo.transcribe(audio_array, language="es", vad_filter=True)
    txt_base = " ".join(s.text for s in segs_base)
    aciertos_base = [t for t in todos_terminos if buscar_termino(t, txt_base)]

    # 2. Initial prompt
    segs_init, _ = modelo.transcribe(audio_array, language="es", vad_filter=True, initial_prompt=glosario_prompt)
    txt_init = " ".join(s.text for s in segs_init)
    aciertos_init = [t for t in todos_terminos if buscar_termino(t, txt_init)]

    # 3. Hotwords
    segs_hot, _ = modelo.transcribe(audio_array, language="es", vad_filter=True, hotwords=glosario_hotwords)
    txt_hot = " ".join(s.text for s in segs_hot)
    aciertos_hot = [t for t in todos_terminos if buscar_termino(t, txt_hot)]

    total = len(todos_terminos)
    rec_base = len(aciertos_base) / total if total > 0 else 0.0
    rec_init = len(aciertos_init) / total if total > 0 else 0.0
    rec_hot = len(aciertos_hot) / total if total > 0 else 0.0

    return {
        "duracion_audio_s": duracion_s,
        "total_terminos": total,
        "tipo_glosario": tipo_glosario,
        "sin_glosario": {
            "detectados": len(aciertos_base),
            "recall": rec_base,
            "terminos_detectados": aciertos_base,
        },
        "initial_prompt": {
            "detectados": len(aciertos_init),
            "recall": rec_init,
            "terminos_detectados": aciertos_init,
        },
        "hotwords": {
            "detectados": len(aciertos_hot),
            "recall": rec_hot,
            "terminos_detectados": aciertos_hot,
        },
        "comparacion_hotwords_vs_initial": {
            "diferencia_aciertos": len(aciertos_hot) - len(aciertos_init),
            "diferencia_pts": (rec_hot - rec_init) * 100.0,
        },
    }


def validar_escritura_resultados(ruta_salida: str | Path | None, modo_simulado: bool) -> None:
    """Prohíbe que el modo simulado escriba o actualice resultados en docs/resultados.md."""
    if not ruta_salida or not modo_simulado:
        return
    p = Path(ruta_salida).resolve()
    if p.name.lower() == "resultados.md" or ("docs" in p.parts and "resultados" in p.stem.lower()):
        raise PermissionError(
            "El modo --simulado tiene prohibido escribir o actualizar docs/resultados.md. "
            "Solo las corridas con audio real alimentan H1."
        )


def imprimir_reporte(resultado: dict[str, Any]) -> None:
    """Imprime el reporte estructurado de evaluación en consola."""
    sin = resultado["sin_glosario"]
    con = resultado["con_glosario"]
    h1 = resultado["hipotesis_h1"]

    metodo = resultado.get("metodo_inyeccion", "initial_prompt")
    tipo_glo = resultado.get("tipo_glosario", "filtrado")

    print("=" * 70)
    print("EVALUACIÓN DE TÉRMINOS ES-EN - HIPÓTESIS H1")
    if resultado["modo"] == "simulado":
        print("SIMULADO: no es una medición")
    print("=" * 70)
    print(f"Modo de ejecución: {resultado['modo']} | Tipo glosario: {tipo_glo} | Inyección: {metodo}")
    if resultado["modo"] == "simulado":
        print("SIMULADO: no es una medición")
    print(f"Total de frases evaluadas: {sin['total_frases']}")
    print("-" * 70)
    print("Línea base (sin glosario):")
    print(f"  Términos esperados : {sin['total_esperados']}")
    print(f"  Términos detectados: {sin['total_detectados']}")
    print(f"  Recall             : {sin['recall_global'] * 100:.2f} %")
    print()
    print(f"Con glosario ({tipo_glo} via {metodo}):")
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


def imprimir_reporte_clip_5min(resultado: dict[str, Any]) -> None:
    """Imprime el reporte comparativo del clip de 5 minutos en consola."""
    print("=" * 70)
    print("EVALUACIÓN CONTINUA EN CLIP DE ~5 MINUTOS - INITIAL_PROMPT VS HOTWORDS")
    print("=" * 70)
    print(f"Duración audio: {resultado['duracion_audio_s']:.1f} s | Glosario: {resultado['tipo_glosario']}")
    print(f"Total términos esperados: {resultado['total_terminos']}")
    print("-" * 70)
    print(f"Sin glosario   : {resultado['sin_glosario']['detectados']}/{resultado['total_terminos']} ({resultado['sin_glosario']['recall'] * 100:.1f} %)")
    print(f"Initial prompt : {resultado['initial_prompt']['detectados']}/{resultado['total_terminos']} ({resultado['initial_prompt']['recall'] * 100:.1f} %)")
    print(f"Hotwords       : {resultado['hotwords']['detectados']}/{resultado['total_terminos']} ({resultado['hotwords']['recall'] * 100:.1f} %)")
    print("-" * 70)
    comp = resultado["comparacion_hotwords_vs_initial"]
    print(f"Diferencia (Hotwords - Initial prompt): {comp['diferencia_aciertos']:+d} términos ({comp['diferencia_pts']:+.2f} pts)")
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
        "--tipo-glosario",
        choices=["producto", "filtrado"],
        default="producto",
        help="Tipo de glosario a emplear: 'producto' (fijado a priori) o 'filtrado' (de frases).",
    )
    parser.add_argument(
        "--metodo-inyeccion",
        choices=["hotwords", "initial_prompt"],
        default="hotwords",
        help="Método de inyección en faster-whisper: 'hotwords' o 'initial_prompt' (default: hotwords).",
    )
    parser.add_argument(
        "--clip-5min",
        action="store_true",
        help="Ejecuta la evaluación sobre el clip continuo de 5 min comparando initial_prompt vs hotwords.",
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

    if args.clip_5min:
        if not args.audios:
            print("ERROR: --clip-5min requiere especificar el directorio de audios con --audios", file=sys.stderr)
            return 1
        res_clip = evaluar_clip_5min(
            directorio_audios=args.audios,
            frases=frases,
            modelo_whisper=args.modelo,
            tipo_glosario=args.tipo_glosario,
        )
        imprimir_reporte_clip_5min(res_clip)
        if args.salida:
            with open(args.salida, "w", encoding="utf-8") as f:
                json.dump(res_clip, f, indent=2, ensure_ascii=False)
        return 0

    resultado = ejecutar_evaluacion(
        frases=frases,
        directorio_audios=args.audios,
        modelo_whisper=args.modelo,
        modo_simulado=args.simulado,
        tipo_glosario=args.tipo_glosario,
        metodo_inyeccion=args.metodo_inyeccion,
    )

    imprimir_reporte(resultado)

    if args.salida:
        salida_path = Path(args.salida)
        try:
            validar_escritura_resultados(
                salida_path, modo_simulado=(args.simulado or resultado["modo"] == "simulado")
            )
        except PermissionError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
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
            "tipo_glosario": resultado.get("tipo_glosario"),
            "metodo_inyeccion": resultado.get("metodo_inyeccion"),
        }
        with open(salida_path, "w", encoding="utf-8") as f:
            json.dump(datos_guardar, f, indent=2, ensure_ascii=False)
        print(f"Reporte guardado exitosamente en: {salida_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
