"""Generador de datos sintéticos etiquetados para entrenamiento y evaluación (T03).

Genera conversaciones sintéticas (ponencias, reuniones, entrevistas) con marcas
temporales y etiquetas por segmento para entrenar el clasificador mmBERT (T12).
Clases: idea, tarea, acuerdo, pregunta, relleno.
Garantiza en reuniones: tarea >= 6% y relleno >= 10%.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

EtiquetaClase = Literal["idea", "tarea", "acuerdo", "pregunta", "relleno"]
TipoConversacion = Literal["ponencia", "reunion", "entrevista"]

CLASES_VALIDAS: list[EtiquetaClase] = ["idea", "tarea", "acuerdo", "pregunta", "relleno"]
TIPOS_VALIDOS: list[TipoConversacion] = ["ponencia", "reunion", "entrevista"]


class SegmentoSintetico(BaseModel):
    """Segmento individual de audio sintético con etiqueta supervisada."""

    id: int | str
    inicio_s: float = Field(..., ge=0.0, description="Tiempo de inicio en segundos")
    fin_s: float = Field(..., ge=0.0, description="Tiempo de fin en segundos")
    texto: str = Field(..., description="Texto del segmento")
    etiqueta: EtiquetaClase = Field(..., description="Clase para mmBERT (5 clases)")
    orador: str | None = Field(default=None, description="Identificador del orador")

    @model_validator(mode="after")
    def _validar_intervalo(self) -> SegmentoSintetico:
        if self.fin_s < self.inicio_s:
            raise ValueError(f"fin_s ({self.fin_s}) no puede ser menor que inicio_s ({self.inicio_s})")
        return self


class ConversacionSintetica(BaseModel):
    """Conversación sintética completa con metadatos y lista de segmentos."""

    id: str
    tipo: TipoConversacion
    titulo: str
    duracion_s: float = Field(..., ge=0.0)
    segmentos: list[SegmentoSintetico]


class DatasetSintetico(BaseModel):
    """Contenedor de dataset con estadísticas y colecciones sintéticas."""

    total_conversaciones: int
    total_segmentos: int
    conteo_por_clase: dict[str, int]
    proporciones_por_clase: dict[str, float]
    conversaciones: list[ConversacionSintetica]


# ---------------------------------------------------------------------------
# Banco de plantillas textuales realistas para modo determinista (dry-run)
# con jerga obligatoria ES-EN en investigación y ciencia de datos.
# ---------------------------------------------------------------------------

BANCO_TEXTOS: dict[TipoConversacion, dict[EtiquetaClase, list[str]]] = {
    "ponencia": {
        "idea": [
            "La reproducibilidad computacional requiere publicar el dataset completo junto al código fuente.",
            "Para someter a un journal indexado en Scopus debemos justificar el valor metodológico del modelo.",
            "El depósito previo en un servidor de preprint acelera la visibilidad de los resultados preliminares.",
            "El análisis de regresión muestra coeficientes significativos luego del control por sesgo de selección.",
            "Un error habitual al redactar el paper es omitir la justificación del tamaño de la muestra observada.",
            "El peer review riguroso suele exigir contrastar la propuesta frente a dos líneas base adicionales.",
            "Las políticas de acceso abierto de este publisher contemplan la exención parcial del pago de APC.",
            "El benchmark sobre el modelo mmBERT demuestra mayor precisión en clasificación de textos breves.",
            "La arquitectura propuesta reduce el tiempo de cómputo en inferencia sin perder sensibilidad.",
            "Los evaluadores metodológicos del grant solicitaron una auditoría detallada de la limpieza de datos.",
        ],
        "tarea": [
            "La asistente Andrea debe consolidar el dataset anonimizado antes del lunes al mediodía.",
            "El equipo de coautores debe formatear la bibliografía siguiendo estrictamente la guía del journal.",
            "Debemos redactar la carta de refutación para los revisores del peer review antes del deadline fijado.",
            "Carlos tiene asignado subir el script de limpieza con la semilla fija al repositorio institucional.",
            "Coordinemos la solicitud formal de fondos para cubrir el APC con la oficina de administración.",
        ],
        "acuerdo": [
            "Quedamos en priorizar el envío del paper al journal del primer cuartil de Scopus.",
            "Acordamos fijar la semilla aleatoria en cuarenta y dos para todas las corridas experimentales.",
            "Se acordó reservar el veinte por ciento de los recursos del grant para actividades de difusión.",
            "Convenimos en liberar una versión preprint una vez concluida la revisión interna entre coautores.",
        ],
        "pregunta": [
            "¿Cuál es el plazo perentorio para enviar las correcciones solicitadas por el editor jefe?",
            "¿Disponemos de presupuesto remanente en el grant para financiar el APC en modalidad open access?",
            "¿Es obligatorio compartir el código de entrenamiento si se emplean bibliotecas propietarias?",
            "¿Qué métrica de validación cruzada solicitó el segundo revisor durante el peer review?",
        ],
        "relleno": [
            "Buenos días con todos los docentes e investigadores que nos acompañan en esta sesión.",
            "Muchas gracias a la comisión organizadora por la cordial invitación a este seminario.",
            "Bien, pasando al siguiente punto de nuestra agenda metodológica...",
            "Agradezco su atención prestada y daremos paso al siguiente bloque temático.",
            "Por favor confirmen si logran visualizar la pantalla compartida adecuadamente.",
            "Un instante mientras se proyectan las diapositivas con los resultados experimentales.",
        ],
    },
    "reunion": {
        "idea": [
            "El rendimiento de mmBERT-small supera a la alternativa tradicional en secuencias con ruido léxico.",
            "Considero que debemos separar los segmentos de relleno antes de enviar el texto al módulo de estructuración.",
            "La latencia de transcripción con faster-whisper en int8 es suficientemente baja para teléfonos móviles.",
            "El glosario personalizado en el prompt inicial redujo notablemente las alucinaciones de términos técnicos.",
            "Un mapa mental con citas literales aporta mayor confianza al usuario que un resumen genérico.",
            "El costo por hora de audio procesado será el elemento determinante para definir los planes de suscripción.",
            "Si la conexión es inestable, la aplicación debe operar fluidamente en modo demostración local.",
            "Los resultados preliminares respaldan la hipótesis de ahorro computacional gracias al detector temprano.",
        ],
        "tarea": [
            "Andrea, por favor verifica que el dataset sintético cumpla con la distribución de clases requerida.",
            "Rodrigo, debes preparar el entorno de Streamlit y configurar los secrets antes de la prueba en la nube.",
            "Revisemos todos el borrador del README para asegurar que las nueve secciones estén completas.",
            "El equipo de NLP debe ejecutar el notebook de fine-tuning y registrar los pesos finales en el repositorio.",
            "Es necesario correr la suite completa de pruebas unitarias y verificar que scripts/verificar.py pase.",
            "Debemos actualizar la hoja de evaluación con las métricas obtenidas antes de las seis de la tarde.",
            "Mariana, encárgate de grabar el clip de audio de prueba con el teléfono celular en la sala silenciosa.",
            "Coordinemos una llamada rápida mañana a las nueve para validar el video de demostración.",
        ],
        "acuerdo": [
            "Quedamos en utilizar mmBERT-small como detector principal por su bajo consumo de memoria RAM.",
            "Acordamos congelar el contrato Pydantic v2 para no generar conflictos entre los módulos del sistema.",
            "Se aprueba mantener tres planes comerciales sencillos para la propuesta de modelo de negocio.",
            "Decidimos no versionar ningún archivo de audio en el repositorio para preservar la privacidad de los datos.",
            "Convenimos en presentar la demo interactiva basada en el mapa mental con markmap durante el pitch.",
        ],
        "pregunta": [
            "¿Logramos mantener el consumo de memoria por debajo de los dos punto siete gigabytes en Streamlit Cloud?",
            "¿Qué recall obtuvimos en la detección de tareas explícitas sobre la reunión actuada?",
            "¿Falta alguna credencial en el archivo .env.example para ejecutar la aplicación en local?",
            "¿A qué hora cerramos el registro del issue de GitHub para cumplir con el deadline de entrega?",
            "¿Quién se encarga de corroborar que no haya secretos expuestos en el historial de commits?",
        ],
        "relleno": [
            "Buenos días equipo, iniciemos puntualmente la reunión de coordinación de hoy.",
            "Hola a todos, ¿se me escucha bien?",
            "Sí, claro, te escuchamos perfectamente.",
            "Un momento que estoy abriendo el documento con los pendientes de la semana.",
            "Perfecto, continuemos entonces con el siguiente punto de la agenda.",
            "Muchas gracias a todos por conectarse a la sesión.",
            "Exactamente, coincido con lo mencionado.",
            "Permítanme un segundo para tomar nota de este comentario.",
        ],
    },
    "entrevista": {
        "idea": [
            "Cuando dirijo una tesis, dedico varias horas a revisar borradores que no citan adecuadamente la literatura.",
            "El mayor obstáculo en consultoría es transcribir entrevistas extensas sin perder el contexto técnico.",
            "Los profesionales del sector público necesitan procesar información sensible de manera estrictamente local.",
            "Herramientas con hardware dedicado son costosas para investigadores en economías emergentes.",
            "Poder hacer clic en una rama del mapa mental y escuchar el minuto exacto ahorra horas de revisión manual.",
            "La mezcla espontánea de español e inglés es muy frecuente en reuniones de tecnología y finanzas.",
        ],
        "tarea": [
            "Por favor envíeme el enlace a la versión beta de la herramienta para probarla con mis grabaciones.",
            "Debo consultar con el comité de ética institucional el protocolo de consentimiento para entrevistas grabadas.",
            "Agendemos una segunda sesión de retroalimentación una vez que hayan probado el prototipo en celular.",
        ],
        "acuerdo": [
            "Acepto participar en el estudio de usuarios siempre que las notas se publiquen de forma anonimizada.",
            "Quedamos en que me compartirán el resumen estructurado generado a partir de este audio de prueba.",
        ],
        "pregunta": [
            "¿Con qué frecuencia graba reuniones de trabajo o ponencias académicas durante el mes?",
            "¿Estaría dispuesto a pagar una suscripción accesible si la herramienta funciona desde su propio teléfono?",
            "¿Qué aplicación utiliza actualmente para tomar notas y organizar los compromisos discutidos?",
            "¿Considera que la privacidad de los datos procesados es un requisito imprescindible para su institución?",
        ],
        "relleno": [
            "Muchas gracias por concedernos esta entrevista para nuestro proyecto de investigación.",
            "No hay de qué, es un placer colaborar con ustedes.",
            "Comprendo perfectamente la situación que me describe.",
            "Claro, por supuesto.",
            "Muy interesante lo que señala, tomamos nota de ello.",
            "Con esto concluimos la entrevista, agradecemos profundamente su tiempo y aportes.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Generación determinista (dry-run)
# ---------------------------------------------------------------------------

def generar_conversacion_sintetica_dry_run(
    tipo: TipoConversacion,
    indice: int,
    num_segmentos: int = 80,
    seed: int = 42,
) -> ConversacionSintetica:
    """Genera una conversación sintética determinista con distribución controlada.

    Para reuniones asegura:
      - tarea >= 6% (típicamente ~12%)
      - relleno >= 10% (típicamente ~15%)
    """
    rng = random.Random(seed + indice * 1000 + hash(tipo) % 10000)

    # Definir pesos por clase según tipo de conversación
    if tipo == "reunion":
        # Asegurar sólidamente tarea >= 6% y relleno >= 10%
        pesos = {
            "idea": 0.45,
            "tarea": 0.12,     # 12% >= 6%
            "relleno": 0.15,   # 15% >= 10%
            "acuerdo": 0.13,
            "pregunta": 0.15,
        }
        titulo = f"Reunión de coordinación de proyecto Minuta #{indice:02d}"
        oradores = ["Moderador", "Andrea", "Rodrigo", "Carlos"]
    elif tipo == "ponencia":
        pesos = {
            "idea": 0.62,
            "tarea": 0.08,
            "relleno": 0.12,
            "acuerdo": 0.06,
            "pregunta": 0.12,
        }
        titulo = f"Ponencia académica sobre ciencia de datos #{indice:02d}"
        oradores = ["Expositor", "Participante"]
    else:  # entrevista
        pesos = {
            "idea": 0.42,
            "pregunta": 0.30,
            "relleno": 0.16,
            "tarea": 0.06,
            "acuerdo": 0.06,
        }
        titulo = f"Entrevista de investigación con usuario potencial #{indice:02d}"
        oradores = ["Entrevistador", "Entrevistado"]

    clases = list(pesos.keys())
    probabilidades = [pesos[c] for c in clases]

    # Asignación determinista garantizando conteos mínimos
    etiquetas_asignadas: list[EtiquetaClase] = []

    if tipo == "reunion":
        min_tarea = max(5, int(num_segmentos * 0.08))
        min_relleno = max(8, int(num_segmentos * 0.12))
        min_acuerdo = max(3, int(num_segmentos * 0.06))
        min_pregunta = max(4, int(num_segmentos * 0.06))

        etiquetas_base: list[EtiquetaClase] = (
            ["tarea"] * min_tarea
            + ["relleno"] * min_relleno
            + ["acuerdo"] * min_acuerdo
            + ["pregunta"] * min_pregunta
        )
        resto = num_segmentos - len(etiquetas_base)
        etiquetas_restantes = rng.choices(clases, weights=probabilidades, k=max(0, resto))
        etiquetas_asignadas = etiquetas_base + etiquetas_restantes
        rng.shuffle(etiquetas_asignadas)
    else:
        # Garantizar que todas las clases aparezcan al menos una vez
        etiquetas_base = [c for c in CLASES_VALIDAS]
        resto = num_segmentos - len(etiquetas_base)
        etiquetas_restantes = rng.choices(clases, weights=probabilidades, k=max(0, resto))
        etiquetas_asignadas = etiquetas_base + etiquetas_restantes
        rng.shuffle(etiquetas_asignadas)

    # Crear segmentos secuenciales con tiempos no decrecientes
    segmentos: list[SegmentoSintetico] = []
    tiempo_actual = 0.0

    banco_tipo = BANCO_TEXTOS[tipo]

    for i, etiqueta in enumerate(etiquetas_asignadas, start=1):
        duracion_seg = rng.uniform(4.0, 9.0)
        inicio = round(tiempo_actual, 1)
        fin = round(tiempo_actual + duracion_seg, 1)
        tiempo_actual = fin + round(rng.uniform(0.2, 1.2), 1)

        lista_frases = banco_tipo[etiqueta]
        frase_base = rng.choice(lista_frases)

        # Variar ligeramente para evitar duplicados exactos repetitivos
        sufijo_variante = ""
        if rng.random() > 0.6:
            variantes = [
                " en esta etapa",
                " según lo planificado",
                " en el marco del proyecto",
                " con el equipo de trabajo",
                " respecto al plazo establecido",
            ]
            sufijo_variante = rng.choice(variantes)

        texto_final = frase_base if not frase_base.endswith(".") else frase_base[:-1] + sufijo_variante + "."
        orador = rng.choice(oradores)

        segmentos.append(
            SegmentoSintetico(
                id=i,
                inicio_s=inicio,
                fin_s=fin,
                texto=texto_final,
                etiqueta=etiqueta,
                orador=orador,
            )
        )

    duracion_total = round(tiempo_actual, 1)

    return ConversacionSintetica(
        id=f"{tipo}_sintetica_{indice:03d}",
        tipo=tipo,
        titulo=titulo,
        duracion_s=duracion_total,
        segmentos=segmentos,
    )


# ---------------------------------------------------------------------------
# Integración con API de Gemini (con fallback a dry-run)
# ---------------------------------------------------------------------------

def generar_conversacion_gemini(
    tipo: TipoConversacion,
    indice: int,
    num_segmentos: int = 80,
    seed: int = 42,
) -> ConversacionSintetica:
    """Genera conversación usando API de Gemini si está disponible; fallback a dry-run."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return generar_conversacion_sintetica_dry_run(tipo, indice, num_segmentos, seed)

    # Intentar google.genai o google.generativeai
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        prompt = (
            f"Genera una transcripción sintética de tipo '{tipo}' para entrenar un modelo clasificador. "
            f"Debe contener exactamente {num_segmentos} segmentos. Cada segmento debe clasificarse en una de "
            f"las siguientes 5 clases: 'idea', 'tarea', 'acuerdo', 'pregunta', 'relleno'. "
            f"Para reuniones, al menos 8% debe ser 'tarea' y al menos 12% 'relleno'. "
            f"Incluye términos en español e inglés técnico de investigación (journal, paper, Scopus, deadline, "
            f"peer review, preprint, grant, dataset, APC, publisher). "
            f"Utiliza nombres de instituciones y personas totalmente ficticios."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ConversacionSintetica,
                "temperature": 0.0,
            },
        )
        if response.text:
            return ConversacionSintetica.model_validate_json(response.text)
    except Exception as e:
        # Fallback determinista seguro ante falta de conexión o librería
        print(f"[Aviso] Fallback a generador determinista para {tipo}_{indice}: {e}", file=sys.stderr)

    return generar_conversacion_sintetica_dry_run(tipo, indice, num_segmentos, seed)


# ---------------------------------------------------------------------------
# Estadísticas y validación
# ---------------------------------------------------------------------------

def calcular_estadisticas_dataset(dataset: DatasetSintetico) -> dict[str, Any]:
    """Calcula totales, conteos y proporciones por clase en todo el dataset."""
    conteo: dict[str, int] = {c: 0 for c in CLASES_VALIDAS}
    total_segmentos = 0

    for conv in dataset.conversaciones:
        for seg in conv.segmentos:
            conteo[seg.etiqueta] = conteo.get(seg.etiqueta, 0) + 1
            total_segmentos += 1

    proporciones: dict[str, float] = {}
    if total_segmentos > 0:
        for c, cant in conteo.items():
            proporciones[c] = round(cant / total_segmentos, 4)

    return {
        "total_conversaciones": len(dataset.conversaciones),
        "total_segmentos": total_segmentos,
        "conteo_por_clase": conteo,
        "proporciones_por_clase": proporciones,
    }


def validar_distribucion_reuniones(dataset: DatasetSintetico) -> tuple[bool, str]:
    """Verifica si en las reuniones del dataset se cumple: tarea >= 6% y relleno >= 10%."""
    reuniones = [c for c in dataset.conversaciones if c.tipo == "reunion"]
    if not reuniones:
        return True, "No hay reuniones en el dataset analizado."

    total_seg = sum(len(c.segmentos) for c in reuniones)
    conteo: dict[str, int] = {c: 0 for c in CLASES_VALIDAS}
    for c in reuniones:
        for s in c.segmentos:
            conteo[s.etiqueta] += 1

    pct_tarea = conteo["tarea"] / total_seg if total_seg > 0 else 0.0
    pct_relleno = conteo["relleno"] / total_seg if total_seg > 0 else 0.0

    cumple_tarea = pct_tarea >= 0.06
    cumple_relleno = pct_relleno >= 0.10

    detalle = (
        f"Reuniones (total={total_seg} seg): "
        f"tarea={pct_tarea:.2%} (req >= 6.0%), "
        f"relleno={pct_relleno:.2%} (req >= 10.0%)"
    )

    return (cumple_tarea and cumple_relleno), detalle


def generar_dataset_sintetico(
    n_por_tipo: int = 2,
    tipos: list[TipoConversacion] | None = None,
    segmentos_por_conv: int = 80,
    dry_run: bool = True,
    seed: int = 42,
) -> DatasetSintetico:
    """Genera un dataset sintético completo de conversaciones."""
    if tipos is None:
        tipos = list(TIPOS_VALIDOS)

    conversaciones: list[ConversacionSintetica] = []

    for tipo in tipos:
        for i in range(1, n_por_tipo + 1):
            if dry_run:
                conv = generar_conversacion_sintetica_dry_run(
                    tipo=tipo,
                    indice=i,
                    num_segmentos=segmentos_por_conv,
                    seed=seed,
                )
            else:
                conv = generar_conversacion_gemini(
                    tipo=tipo,
                    indice=i,
                    num_segmentos=segmentos_por_conv,
                    seed=seed,
                )
            conversaciones.append(conv)

    # Calcular estadísticas globales
    conteo: dict[str, int] = {c: 0 for c in CLASES_VALIDAS}
    total_seg = 0
    for conv in conversaciones:
        for s in conv.segmentos:
            conteo[s.etiqueta] += 1
            total_seg += 1

    proporciones = {c: round(cant / total_seg, 4) for c, cant in conteo.items()} if total_seg > 0 else {}

    return DatasetSintetico(
        total_conversaciones=len(conversaciones),
        total_segmentos=total_seg,
        conteo_por_clase=conteo,
        proporciones_por_clase=proporciones,
        conversaciones=conversaciones,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generador de datos sintéticos supervisados para Minuta (T03)."
    )
    parser.add_argument(
        "--n",
        type=int,
        default=2,
        help="Número de conversaciones sintéticas por tipo (default: 2)",
    )
    parser.add_argument(
        "--tipo",
        type=str,
        default="todas",
        choices=["ponencia", "reunion", "entrevista", "todas"],
        help="Tipo de conversación a generar (default: todas)",
    )
    parser.add_argument(
        "--segmentos",
        type=int,
        default=80,
        help="Número de segmentos por conversación (default: 80)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo generador determinista simulado (no requiere GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default=str(ROOT_DIR / "entrenamiento" / "datos" / "sinteticos_muestra.json"),
        help="Ruta al archivo JSON de salida",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=42,
        help="Semilla aleatoria para reproducibilidad (default: 42)",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    parsed = parse_args(args)

    tipos: list[TipoConversacion]
    if parsed.tipo == "todas":
        tipos = list(TIPOS_VALIDOS)
    else:
        tipos = [parsed.tipo]  # type: ignore

    dataset = generar_dataset_sintetico(
        n_por_tipo=parsed.n,
        tipos=tipos,
        segmentos_por_conv=parsed.segmentos,
        dry_run=parsed.dry_run,
        seed=parsed.semilla,
    )

    # Imprimir conteos requeridos por plan maestro §8
    conteos_str = ", ".join(f"{c}={dataset.conteo_por_clase.get(c, 0)}" for c in CLASES_VALIDAS)
    print(f"Conteo por clase: {conteos_str}")

    cumple_reuniones, detalle = validar_distribucion_reuniones(dataset)
    print(f"Distribución reuniones: {detalle} -> {'CUMPLE' if cumple_reuniones else 'FALLA'}")

    # Guardar archivo de salida
    ruta_salida = Path(parsed.salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(dataset.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"Datos sintéticos guardados exitosamente en: {ruta_salida}")
    return 0 if cumple_reuniones else 1


if __name__ == "__main__":
    sys.exit(main())
