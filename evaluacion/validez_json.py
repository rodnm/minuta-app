"""Módulo de evaluación de validez de JSON estructurado con Ollama (evaluacion/validez_json.py).

Evalúa la hipótesis pre-registrada H6 de Minuta:
"Ollama qwen3:4b devuelve JSON válido, incluido el árbol del mapa:
Confirmada si: >= 95% de respuestas devuelven JSON válido y < 60 s por bloque.
Falsada si: < 85% válido o > 120 s por bloque."
"""

from __future__ import annotations

import argparse
from enum import Enum
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Sequence
import urllib.error
import urllib.request

from pydantic import ValidationError

from minuta.esquemas import (
    Evidencia,
    MapaMental,
    NodoMapa,
    Segmento,
    validar_evidencia_literal,
)


# Umbrales pre-registrados para la hipótesis H6
UMBRAL_VALIDEZ_CONFIRMADA: float = 0.95
UMBRAL_TIEMPO_CONFIRMADA_S: float = 60.0
UMBRAL_VALIDEZ_FALSADA: float = 0.85
UMBRAL_TIEMPO_FALSADA_S: float = 120.0


class VeredictoH6(str, Enum):
    """Veredicto formal de la hipótesis H6 bajo el marco HDD."""

    CONFIRMADA = "CONFIRMADA"
    FALSADA = "FALSADA"
    NO_CONCLUYENTE = "NO_CONCLUYENTE"


def evaluar_hipotesis_h6(
    pct_validez: float,
    tiempo_promedio_s: float,
    total_bloques: int = 1,
) -> dict[str, Any]:
    """Aplica la regla de decisión pre-registrada HDD para la hipótesis H6.

    Confirmada si: >= 95% válido y < 60 s por bloque.
    Falsada si: < 85% válido o > 120 s por bloque.
    No concluyente en caso intermedio o si no se alcanzan umbrales extremos.
    """
    validez_pct = pct_validez * 100.0

    if pct_validez < UMBRAL_VALIDEZ_FALSADA or tiempo_promedio_s > UMBRAL_TIEMPO_FALSADA_S:
        veredicto = VeredictoH6.FALSADA
        motivo = (
            f"Falsada: validez ({validez_pct:.1f}%) < {UMBRAL_VALIDEZ_FALSADA*100:.0f}% "
            f"o tiempo promedio ({tiempo_promedio_s:.2f} s) > {UMBRAL_TIEMPO_FALSADA_S:.0f} s por bloque."
        )
    elif pct_validez >= UMBRAL_VALIDEZ_CONFIRMADA and tiempo_promedio_s < UMBRAL_TIEMPO_CONFIRMADA_S:
        veredicto = VeredictoH6.CONFIRMADA
        motivo = (
            f"Confirmada: validez ({validez_pct:.1f}%) >= {UMBRAL_VALIDEZ_CONFIRMADA*100:.0f}% "
            f"y tiempo promedio ({tiempo_promedio_s:.2f} s) < {UMBRAL_TIEMPO_CONFIRMADA_S:.0f} s por bloque."
        )
    else:
        veredicto = VeredictoH6.NO_CONCLUYENTE
        motivo = (
            f"No concluyente: validez ({validez_pct:.1f}%) o tiempo promedio ({tiempo_promedio_s:.2f} s) "
            "en zona intermedia."
        )

    return {
        "pct_validez": pct_validez,
        "tiempo_promedio_s": tiempo_promedio_s,
        "total_bloques": total_bloques,
        "veredicto": veredicto,
        "motivo": motivo,
    }


def cargar_bloques(
    origen: str | Path,
    tamano_bloque: int = 10,
    max_bloques: int | None = None,
) -> list[dict[str, Any]]:
    """Carga segmentos transcritos y los particiona en bloques cronológicos.

    Soporta una ruta a un archivo individual JSON o un directorio con transcripciones (ej. data/fixtures/).
    """
    p = Path(origen)
    if not p.exists():
        raise FileNotFoundError(f"No se encontró la ruta de origen: {p}")

    archivos: list[Path] = []
    if p.is_dir():
        # Preferir transcripciones de fixtures
        archivos = sorted(list(p.glob("transcripcion_*.json")))
        if not archivos:
            archivos = sorted(list(p.glob("*.json")))
    else:
        archivos = [p]

    if not archivos:
        raise ValueError(f"No se encontraron archivos JSON de transcripción en {p}")

    bloques: list[dict[str, Any]] = []

    for arch in archivos:
        try:
            with open(arch, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if not isinstance(data, dict) or "segmentos" not in data:
            continue

        segmentos_raw = data.get("segmentos", [])
        if not isinstance(segmentos_raw, list) or not segmentos_raw:
            continue

        audio_id = str(data.get("audio_id", arch.stem))

        # Particionar en lotes de tamano_bloque
        for i in range(0, len(segmentos_raw), tamano_bloque):
            lote = segmentos_raw[i : i + tamano_bloque]
            if not lote:
                continue

            bloque_id = f"{audio_id}_b{len(bloques) + 1:02d}"
            inicio_s = float(lote[0].get("inicio_s", 0.0))
            fin_s = float(lote[-1].get("fin_s", inicio_s))

            bloques.append({
                "id_bloque": bloque_id,
                "fuente": arch.name,
                "inicio_s": inicio_s,
                "fin_s": fin_s,
                "segmentos": lote,
            })

            if max_bloques is not None and len(bloques) >= max_bloques:
                return bloques

    return bloques


def construir_prompt(bloque: dict[str, Any]) -> str:
    """Construye el prompt en español para solicitar extracción estructurada de MapaMental."""
    segmentos = bloque.get("segmentos", [])
    lineas_segmentos: list[str] = []

    for seg in segmentos:
        sid = seg.get("id")
        ini = seg.get("inicio_s", 0.0)
        fin = seg.get("fin_s", 0.0)
        txt = seg.get("texto", "")
        lineas_segmentos.append(f"[{sid} | {ini:.1f}s - {fin:.1f}s]: {txt}")

    texto_transcripcion = "\n".join(lineas_segmentos)

    prompt = f"""Eres el módulo de estructuración de Minuta. A partir de la siguiente transcripción, extrae las ideas principales y genera un árbol jerárquico de mapa mental (MapaMental) con marcas de tiempo.

INSTRUCCIONES OBLIGATORIAS:
1. Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin formato markdown fuera del JSON.
2. Estructura exacta requerida:
{{
  "titulo": "Título temático del bloque",
  "raiz": {{
    "id": "raiz",
    "titulo": "Tema central abordado",
    "resumen": "Resumen conciso del contenido del bloque",
    "evidencia": null,
    "hijos": [
      {{
        "id": "nodo_1",
        "titulo": "Idea o subtema relevante",
        "resumen": "Explicación breve de la idea",
        "evidencia": {{
          "segmento_ids": [1],
          "inicio_s": 0.0,
          "cita": "cita literal exacta tomada de los segmentos"
        }},
        "hijos": []
      }}
    ]
  }}
}}
3. En cada nodo hijo, 'evidencia.cita' DEBE ser una subcadena textual exacta tomada de los segmentos correspondientes.
4. La raíz tiene 'evidencia': null.

TRANSCRIPCIÓN DEL BLOQUE:
{texto_transcripcion}
"""
    return prompt


def limpiar_texto_json(raw: str) -> str:
    """Extrae el contenido JSON eliminando etiquetas de pensamiento y bloques markdown."""
    texto = raw.strip()

    # Eliminar bloques de pensamiento si existieran en la respuesta (<think>...</think>)
    texto = re.sub(r"<think>[\s\S]*?</think>", "", texto, flags=re.IGNORECASE).strip()

    # Eliminar bloques markdown ```json ... ``` o ``` ... ```
    patron_markdown = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", texto, flags=re.IGNORECASE)
    if patron_markdown:
        texto = patron_markdown.group(1).strip()

    # Si aún no inicia con { o [, buscar el primer {
    if not (texto.startswith("{") or texto.startswith("[")):
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            texto = texto[inicio : fin + 1]

    return texto


def validar_respuesta_json(
    texto_respuesta: str,
    segmentos_bloque: list[Segmento | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Valida sintáctica y semánticamente la respuesta JSON contra el contrato Pydantic.

    Verifica que sea JSON válido y que valide contra el modelo MapaMental (o NodoMapa).
    Opcionalmente verifica citas literales contra los segmentos.
    """
    texto_limpio = limpiar_texto_json(texto_respuesta)

    # 1. Validación sintáctica de JSON
    try:
        obj = json.loads(texto_limpio)
    except Exception as exc:
        return {
            "es_json_valido": False,
            "es_pydantic_valido": False,
            "mapa": None,
            "citas_totales": 0,
            "citas_literales": 0,
            "pct_citas_literales": 0.0,
            "error": f"Error de sintaxis JSON: {exc}",
            "objeto_crudo": None,
        }

    # 2. Validación de contrato Pydantic
    mapa: MapaMental | None = None
    error_pydantic: str | None = None

    try:
        if isinstance(obj, dict):
            if "mapa" in obj and isinstance(obj["mapa"], dict) and "raiz" in obj["mapa"]:
                mapa = MapaMental.model_validate(obj["mapa"])
            elif "raiz" in obj and isinstance(obj["raiz"], dict):
                mapa = MapaMental.model_validate(obj)
            elif "id" in obj and "hijos" in obj:
                nodo_raiz = NodoMapa.model_validate(obj)
                mapa = MapaMental(titulo=obj.get("titulo", "Mapa Mental"), raiz=nodo_raiz)
            else:
                # Intentar validar directamente como MapaMental
                mapa = MapaMental.model_validate(obj)
        else:
            raise ValueError(f"La respuesta JSON debe ser un objeto dict, se recibió {type(obj).__name__}")
    except (ValidationError, ValueError, TypeError) as exc:
        error_pydantic = f"Error de validación Pydantic: {exc}"
        return {
            "es_json_valido": True,
            "es_pydantic_valido": False,
            "mapa": None,
            "citas_totales": 0,
            "citas_literales": 0,
            "pct_citas_literales": 0.0,
            "error": error_pydantic,
            "objeto_crudo": obj,
        }

    # 3. Verificación de citas literales si se proveen segmentos
    citas_totales = 0
    citas_literales = 0

    segmentos_modelo: list[Segmento] = []
    if segmentos_bloque:
        for s in segmentos_bloque:
            if isinstance(s, Segmento):
                segmentos_modelo.append(s)
            elif isinstance(s, dict):
                try:
                    segmentos_modelo.append(Segmento.model_validate(s))
                except Exception:
                    pass

    def _revisar_nodo(nodo: NodoMapa) -> None:
        nonlocal citas_totales, citas_literales
        if nodo.evidencia is not None:
            citas_totales += 1
            if segmentos_modelo and validar_evidencia_literal(nodo.evidencia.cita, segmentos_modelo):
                citas_literales += 1
        for h in nodo.hijos:
            _revisar_nodo(h)

    if mapa is not None:
        _revisar_nodo(mapa.raiz)

    pct_citas = (citas_literales / citas_totales) if citas_totales > 0 else 1.0

    return {
        "es_json_valido": True,
        "es_pydantic_valido": True,
        "mapa": mapa,
        "citas_totales": citas_totales,
        "citas_literales": citas_literales,
        "pct_citas_literales": pct_citas,
        "error": None,
        "objeto_crudo": obj,
    }


def simular_respuesta_ollama(
    bloque: dict[str, Any],
    seed: int = 42,
    prob_valido: float = 1.0,
) -> dict[str, Any]:
    """Genera una respuesta determinista simulada que cumple el contrato MapaMental."""
    rng = random.Random(seed + hash(bloque.get("id_bloque", "")))
    segmentos = bloque.get("segmentos", [])

    if rng.random() > prob_valido:
        # Simular JSON malformado
        return {
            "respuesta": "{ titulo: 'error sintaxis sin comillas' ",
            "duracion_s": 0.5,
            "total_duration_ns": 500000000,
        }

    hijos: list[dict[str, Any]] = []
    for idx, seg in enumerate(segmentos[:3], start=1):
        txt = str(seg.get("texto", ""))
        # Subcadena literal para asegurar fidelidad
        subcadena = txt[: min(len(txt), 40)].strip()
        hijos.append({
            "id": f"nodo_{idx}",
            "titulo": f"Idea clave {idx}",
            "resumen": f"Detalle de la idea {idx}",
            "evidencia": {
                "segmento_ids": [seg.get("id", idx)],
                "inicio_s": float(seg.get("inicio_s", 0.0)),
                "cita": subcadena,
            },
            "hijos": [],
        })

    arbol_mapa = {
        "titulo": f"Mapa del {bloque.get('id_bloque', 'bloque')}",
        "raiz": {
            "id": "raiz",
            "titulo": "Eje Temático Principal",
            "resumen": "Resumen conciso del bloque generado deterministamente",
            "evidencia": None,
            "hijos": hijos,
        },
    }

    return {
        "respuesta": json.dumps(arbol_mapa, ensure_ascii=False, indent=2),
        "duracion_s": 1.25,
        "total_duration_ns": 1250000000,
    }


def llamar_ollama(
    prompt: str,
    host: str = "http://localhost:11434",
    modelo: str = "qwen3:4b",
    temperatura: float = 0.0,
    timeout_s: float = 180.0,
    think: bool = False,
) -> dict[str, Any]:
    """Llama a la API /api/generate de Ollama local solicitando salida JSON.

    Por defecto 'think=False' desactiva la fase de razonamiento verboso en modelos como qwen3,
    asegurando respuesta JSON directa con baja latencia.
    """
    url = f"{host.rstrip('/')}/api/generate"
    payload = {
        "model": modelo,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "think": think,
        "options": {
            "temperature": temperatura,
        },
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
            res_json = json.loads(body)
    except urllib.error.URLError as exc:
        raise ConnectionError(f"No se pudo conectar con Ollama en {url}: {exc}") from exc

    t1 = time.perf_counter()
    duracion_s = t1 - t0

    respuesta_texto = res_json.get("response", "")
    return {
        "respuesta": respuesta_texto,
        "duracion_s": duracion_s,
        "total_duration_ns": res_json.get("total_duration", 0),
        "load_duration_ns": res_json.get("load_duration", 0),
        "eval_count": res_json.get("eval_count", 0),
    }


def ejecutar_evaluacion(
    bloques: Sequence[dict[str, Any]],
    proveedor: str = "ollama",
    host: str = "http://localhost:11434",
    modelo: str = "qwen3:4b",
    simulado: bool = False,
    temperatura: float = 0.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Ejecuta la evaluación completa de validez de JSON sobre los bloques indicados."""
    if not bloques:
        raise ValueError("La lista de bloques a evaluar no puede estar vacía.")

    detalles_bloques: list[dict[str, Any]] = []
    tiempos_s: list[float] = []
    json_validos = 0
    pydantic_validos = 0
    citas_totales_global = 0
    citas_literales_global = 0

    for idx, bloque in enumerate(bloques, start=1):
        prompt = construir_prompt(bloque)

        if simulado:
            res_ollama = simular_respuesta_ollama(bloque, seed=seed + idx)
        else:
            res_ollama = llamar_ollama(
                prompt=prompt,
                host=host,
                modelo=modelo,
                temperatura=temperatura,
            )

        duracion_s = float(res_ollama.get("duracion_s", 0.0))
        tiempos_s.append(duracion_s)

        validacion = validar_respuesta_json(
            texto_respuesta=res_ollama.get("respuesta", ""),
            segmentos_bloque=bloque.get("segmentos", []),
        )

        if validacion["es_json_valido"]:
            json_validos += 1
        if validacion["es_pydantic_valido"]:
            pydantic_validos += 1

        citas_totales_global += validacion.get("citas_totales", 0)
        citas_literales_global += validacion.get("citas_literales", 0)

        detalles_bloques.append({
            "bloque_id": bloque.get("id_bloque"),
            "fuente": bloque.get("fuente"),
            "duracion_bloque_s": bloque.get("fin_s", 0.0) - bloque.get("inicio_s", 0.0),
            "tiempo_respuesta_s": duracion_s,
            "es_json_valido": validacion["es_json_valido"],
            "es_pydantic_valido": validacion["es_pydantic_valido"],
            "citas_totales": validacion["citas_totales"],
            "citas_literales": validacion["citas_literales"],
            "error": validacion["error"],
        })

    total_bloques = len(bloques)
    pct_json = (json_validos / total_bloques) if total_bloques > 0 else 0.0
    pct_pydantic = (pydantic_validos / total_bloques) if total_bloques > 0 else 0.0
    tiempo_promedio = (sum(tiempos_s) / len(tiempos_s)) if tiempos_s else 0.0

    veredicto_h6 = evaluar_hipotesis_h6(
        pct_validez=pct_pydantic,
        tiempo_promedio_s=tiempo_promedio,
        total_bloques=total_bloques,
    )

    pct_citas_global = (
        (citas_literales_global / citas_totales_global)
        if citas_totales_global > 0
        else 1.0
    )

    return {
        "proveedor": proveedor,
        "modelo": modelo,
        "modo_simulado": simulado,
        "total_bloques": total_bloques,
        "total_json_validos": json_validos,
        "pct_json_valido": pct_json,
        "total_pydantic_validos": pydantic_validos,
        "pct_validez": pct_pydantic,
        "tiempo_total_s": sum(tiempos_s),
        "tiempo_promedio_s": tiempo_promedio,
        "tiempos_s": tiempos_s,
        "citas_totales": citas_totales_global,
        "citas_literales": citas_literales_global,
        "pct_citas_literales": pct_citas_global,
        "veredicto_h6": veredicto_h6,
        "detalles_bloques": detalles_bloques,
    }


def imprimir_reporte(res: dict[str, Any]) -> None:
    """Imprime el resumen de evaluación y el veredicto HDD en español neutro."""
    ver = res["veredicto_h6"]
    print("=" * 65)
    print("  EVALUACIÓN DE JSON ESTRUCTURADO - HIPÓTESIS H6 (OLLAMA)")
    print("=" * 65)
    print(f"Proveedor              : {res['proveedor']}")
    print(f"Modelo                 : {res['modelo']}")
    print(f"Modo simulado          : {'SÍ' if res['modo_simulado'] else 'NO (Ollama real)'}")
    print(f"Total bloques          : {res['total_bloques']}")
    print(f"JSON sintáctico válido : {res['total_json_validos']}/{res['total_bloques']} ({res['pct_json_valido']*100:.1f}%)")
    print(f"Contrato Pydantic OK   : {res['total_pydantic_validos']}/{res['total_bloques']} ({res['pct_validez']*100:.1f}%)")
    print(f"Citas literales        : {res['citas_literales']}/{res['citas_totales']} ({res['pct_citas_literales']*100:.1f}%)")
    print(f"Tiempo total           : {res['tiempo_total_s']:.2f} s")
    print(f"Tiempo promedio/bloque : {res['tiempo_promedio_s']:.2f} s")
    if res["tiempos_s"]:
        print(f"Tiempos individuales   : {[round(t, 2) for t in res['tiempos_s']]} s")
    print("-" * 65)
    print(f"VEREDICTO H6           : {ver['veredicto'].value}")
    print(f"Motivo                 : {ver['motivo']}")
    print("=" * 65)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI para evaluacion.validez_json."""
    parser = argparse.ArgumentParser(
        description="Evalúa la hipótesis H6 de Minuta: validez y latencia de JSON estructurado con Ollama.",
    )
    parser.add_argument(
        "--proveedor",
        default="ollama",
        choices=["ollama"],
        help="Proveedor de inferencia local (default: ollama).",
    )
    parser.add_argument(
        "--modelo",
        default="qwen3:4b",
        help="Modelo a emplear en Ollama (default: qwen3:4b).",
    )
    parser.add_argument(
        "--bloques",
        default="data/fixtures/",
        help="Ruta al directorio de fixtures o archivo de transcripción individual.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        help="Número máximo de bloques a evaluar.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        help="Host del servidor Ollama (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--tamano_bloque",
        type=int,
        default=10,
        help="Cantidad de segmentos por bloque (default: 10).",
    )
    parser.add_argument(
        "--temperatura",
        type=float,
        default=0.0,
        help="Temperatura de inferencia (default: 0.0).",
    )
    parser.add_argument(
        "--simulado",
        action="store_true",
        help="Ejecuta en modo simulado determinista sin realizar llamadas de red a Ollama.",
    )
    parser.add_argument(
        "--salida",
        default=None,
        help="Ruta opcional para guardar el reporte en formato JSON.",
    )

    args = parser.parse_args(argv)

    try:
        bloques = cargar_bloques(
            origen=args.bloques,
            tamano_bloque=args.tamano_bloque,
            max_bloques=args.n,
        )
    except Exception as exc:
        print(f"Error cargando bloques: {exc}", file=sys.stderr)
        return 1

    if not bloques:
        print(f"No se obtuvieron bloques para evaluar desde {args.bloques}", file=sys.stderr)
        return 1

    try:
        resultado = ejecutar_evaluacion(
            bloques=bloques,
            proveedor=args.proveedor,
            host=args.host,
            modelo=args.modelo,
            simulado=args.simulado,
            temperatura=args.temperatura,
        )
    except Exception as exc:
        print(f"Error durante la evaluación: {exc}", file=sys.stderr)
        return 1

    imprimir_reporte(resultado)

    if args.salida:
        salida_path = Path(args.salida)
        salida_path.parent.mkdir(parents=True, exist_ok=True)
        datos_guardar = {
            **resultado,
            "veredicto_h6": {
                **resultado["veredicto_h6"],
                "veredicto": resultado["veredicto_h6"]["veredicto"].value,
            },
        }
        with open(salida_path, "w", encoding="utf-8") as f:
            json.dump(datos_guardar, f, indent=2, ensure_ascii=False)
        print(f"Reporte guardado exitosamente en: {salida_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
