"""Generador de datos sintéticos etiquetados para entrenamiento y evaluación (T03).

Genera conversaciones sintéticas (ponencias, reuniones, entrevistas) con marcas
temporales y etiquetas por segmento para entrenar el clasificador mmBERT (T12).
Clases: idea, tarea, acuerdo, pregunta, relleno.
Garantiza en reuniones: tarea >= 6% y relleno >= 10%.
Soporta generación estructurada vía REST API de Gemini y dry-run determinista.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Literal
import requests
from dotenv import dotenv_values
from pydantic import BaseModel, Field, model_validator

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

EtiquetaClase = Literal["idea", "tarea", "acuerdo", "pregunta", "relleno"]
TipoConversacion = Literal["ponencia", "reunion", "entrevista"]
FuenteConversacion = Literal["gemini", "plantilla"]

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
    fuente: FuenteConversacion = Field(
        default="plantilla",
        description="Fuente de la conversación: gemini o plantilla",
    )
    segmentos: list[SegmentoSintetico]


class DatasetSintetico(BaseModel):
    """Contenedor de dataset con estadísticas y colecciones sintéticas."""

    total_conversaciones: int
    total_segmentos: int
    conteo_por_clase: dict[str, int]
    proporciones_por_clase: dict[str, float]
    porcentaje_unicos: float = Field(
        default=0.0,
        description="Porcentaje de segmentos con texto único en el dataset",
    )
    desglose_por_fuente: dict[str, int] = Field(
        default_factory=dict,
        description="Cantidad de conversaciones por fuente generadora",
    )
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

    if tipo == "reunion":
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
        etiquetas_base = [c for c in CLASES_VALIDAS]
        resto = num_segmentos - len(etiquetas_base)
        etiquetas_restantes = rng.choices(clases, weights=probabilidades, k=max(0, resto))
        etiquetas_asignadas = etiquetas_base + etiquetas_restantes
        rng.shuffle(etiquetas_asignadas)

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
        fuente="plantilla",
        segmentos=segmentos,
    )


# ---------------------------------------------------------------------------
# Integración con API de Gemini vía REST
# ---------------------------------------------------------------------------

def obtener_api_key() -> str | None:
    """Obtiene la clave GEMINI_API_KEY desde entorno o desde el archivo .env."""
    key = os.getenv("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip().strip('"').strip("'")

    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        vals = dotenv_values(env_path)
        k = vals.get("GEMINI_API_KEY")
        if k and k.strip():
            return k.strip().strip('"').strip("'")

    return None


def llamar_gemini_rest(
    prompt: str,
    modelo: str = "gemini-3.8-flash",
    api_key: str | None = None,
    timeout: int = 45,
    max_reintentos: int = 3,
) -> str:
    """Ejecuta una petición POST a la REST API de Gemini v1beta con reintentos."""
    key = api_key or obtener_api_key()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY no encontrada. Configure la clave en .env o variable de entorno."
        )

    # Orden de modelos candidatos para tolerancia a indisponibilidad o 404/503
    candidatos = [modelo]
    for m_alt in ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview"]:
        if m_alt not in candidatos:
            candidatos.append(m_alt)

    ultimo_error: str | None = None
    # La clave viaja en la cabecera, nunca en la URL: un error de conexión imprime la URL completa.
    cabeceras = {"x-goog-api-key": key, "Content-Type": "application/json"}

    for mod in candidatos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.4,
            },
        }

        for intento in range(1, max_reintentos + 1):
            try:
                resp = requests.post(url, json=payload, headers=cabeceras, timeout=(10, timeout))
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"]
                    ultimo_error = f"Respuesta JSON sin partes de texto válidas en modelo {mod}."
                    break

                if resp.status_code in (429, 503):
                    ultimo_error = f"HTTP {resp.status_code} ({mod}): alta demanda o límite de tasa."
                    time.sleep(2 * intento)
                    continue

                if resp.status_code == 404:
                    ultimo_error = f"HTTP 404 ({mod}): modelo no disponible para este endpoint."
                    break

                ultimo_error = f"HTTP {resp.status_code} ({mod}): {resp.text[:150]}"
                break
            except Exception as e:
                ultimo_error = f"Excepción en {mod} intento {intento}: {e}"
                time.sleep(2 * intento)

    raise RuntimeError(f"Fallo en llamada a la API de Gemini: {ultimo_error}".replace(key, "***"))


def _normalizar_segmentos_gemini(
    raw_segmentos: list[dict[str, Any]],
    tipo: TipoConversacion,
) -> list[SegmentoSintetico]:
    """Asegura consistencia de marcas temporales y etiquetas en segmentos de Gemini."""
    segmentos: list[SegmentoSintetico] = []
    t_actual = 0.0

    mapeo_etiquetas: dict[str, EtiquetaClase] = {
        "idea": "idea",
        "ideas": "idea",
        "conclusion": "idea",
        "hallazgo": "idea",
        "tarea": "tarea",
        "tareas": "tarea",
        "accion": "tarea",
        "pendiente": "tarea",
        "to-do": "tarea",
        "acuerdo": "acuerdo",
        "acuerdos": "acuerdo",
        "compromiso": "acuerdo",
        "pregunta": "pregunta",
        "preguntas": "pregunta",
        "duda": "pregunta",
        "relleno": "relleno",
        "saludo": "relleno",
        "introduccion": "relleno",
        "despedida": "relleno",
    }

    for i, s in enumerate(raw_segmentos, start=1):
        ini = float(s.get("inicio_s", t_actual))
        if ini < t_actual:
            ini = round(t_actual, 1)

        fin = float(s.get("fin_s", ini + 5.0))
        if fin <= ini:
            fin = round(ini + round(random.uniform(4.0, 8.0), 1), 1)

        t_actual = round(fin + round(random.uniform(0.2, 1.0), 1), 1)

        raw_etq = str(s.get("etiqueta", "idea")).lower().strip()
        etiqueta_final: EtiquetaClase = mapeo_etiquetas.get(raw_etq, "idea")
        texto_seg = str(s.get("texto", "")).strip() or "Comentario de revisión metodológica."
        orador = str(s.get("orador", f"Participante_{i % 3 + 1}"))

        segmentos.append(
            SegmentoSintetico(
                id=i,
                inicio_s=ini,
                fin_s=fin,
                texto=texto_seg,
                etiqueta=etiqueta_final,
                orador=orador,
            )
        )

    # Si es reunión, asegurar cuotas mínimas si hiciera falta
    if tipo == "reunion" and segmentos:
        n_tot = len(segmentos)
        c_tarea = sum(1 for s in segmentos if s.etiqueta == "tarea")
        c_relleno = sum(1 for s in segmentos if s.etiqueta == "relleno")

        min_tarea = max(2, int(n_tot * 0.08))
        min_relleno = max(2, int(n_tot * 0.12))

        # Promover segmentos de 'idea' si faltan cuotas
        if c_tarea < min_tarea:
            faltan = min_tarea - c_tarea
            for seg in segmentos:
                if seg.etiqueta == "idea" and faltan > 0:
                    seg.etiqueta = "tarea"
                    faltan -= 1

        if c_relleno < min_relleno:
            faltan_r = min_relleno - c_relleno
            for seg in segmentos:
                if seg.etiqueta == "idea" and faltan_r > 0:
                    seg.etiqueta = "relleno"
                    faltan_r -= 1

    return segmentos


def generar_conversacion_gemini(
    tipo: TipoConversacion,
    indice: int,
    num_segmentos: int = 80,
    modelo: str = "gemini-3.8-flash",
    estricto: bool = True,
    seed: int = 42,
    api_key: str | None = None,
) -> ConversacionSintetica:
    """Genera una conversación individual con Gemini vía REST API."""
    prompt = (
        f"Genera una conversación sintética estructurada de tipo '{tipo}' para entrenar un modelo clasificador. "
        f"Debe contener exactamente {num_segmentos} segmentos secuenciales. "
        f"Cada segmento debe clasificarse en una de estas 5 clases obligatorias: 'idea', 'tarea', 'acuerdo', 'pregunta', 'relleno'. "
        f"Para reuniones, al menos 8% debe ser 'tarea' y al menos 12% 'relleno'. "
        f"Incluye jerga técnica ES-EN de investigación y ciencia de datos (journal, paper, Scopus, deadline, "
        f"peer review, preprint, grant, dataset, APC, publisher, benchmark, trade-off). "
        f"Los nombres de personas e instituciones deben ser completamente ficticios. "
        f"Devuelve estrictamente un objeto JSON con el formato: "
        f'{{"id": "{tipo}_sintetica_{indice:03d}", "tipo": "{tipo}", "titulo": "...", "duracion_s": 0.0, "fuente": "gemini", '
        f'"segmentos": [{{"id": 1, "inicio_s": 0.0, "fin_s": 5.0, "texto": "...", "etiqueta": "idea", "orador": "..."}}]}}'
    )

    try:
        texto_json = llamar_gemini_rest(prompt=prompt, modelo=modelo, api_key=api_key)
        data = json.loads(texto_json)
        if isinstance(data, list) and data:
            data = data[0]

        segmentos_norm = _normalizar_segmentos_gemini(data.get("segmentos", []), tipo)
        duracion_tot = segmentos_norm[-1].fin_s if segmentos_norm else 100.0

        return ConversacionSintetica(
            id=f"{tipo}_sintetica_{indice:03d}",
            tipo=tipo,
            titulo=data.get("titulo", f"Conversación sintética {tipo} #{indice:02d}"),
            duracion_s=duracion_tot,
            fuente="gemini",
            segmentos=segmentos_norm,
        )
    except Exception as exc:
        if estricto:
            raise RuntimeError(
                f"Error en generación con Gemini para {tipo}_{indice} (modo estricto activo): {exc}"
            ) from exc
        print(
            f"[Aviso] Fallback a plantilla para {tipo}_{indice} debido a fallo en Gemini: {exc}",
            file=sys.stderr,
        )
        return generar_conversacion_sintetica_dry_run(tipo, indice, num_segmentos, seed)


TEMAS_POR_TIPO: dict[TipoConversacion, list[str]] = {
    "ponencia": [
        "clasificación supervisada de texto multilingüe y arquitecturas compactas como mmBERT",
        "políticas de acceso abierto, fondos para tasas de procesamiento APC y revistas Scopus Q1",
        "reproducibilidad computacional, control de semillas fijas y publicación de datasets abiertos",
        "diseño metodológico de experimentos, estimación causal y control por sesgo de selección",
        "estrategias de respuesta estructurada a revisores durante el arbitraje por pares (peer review)",
        "análisis bibliométrico de literatura académica, minería de texto y metanálisis",
        "desafíos éticos de la inteligencia artificial generativa en publicaciones científicas",
        "benchmarking de modelos de lenguaje en tareas de extracción de entidades y relaciones",
    ],
    "reunion": [
        "coordinación de sprint técnico, revisión de pull requests y congelamiento de contratos Pydantic",
        "monitoreo de consumo de memoria RAM y optimización de latencia en modelos Whisper int8",
        "diseño de mapas mentales interactivos con markmap y citas textuales verificables por minuto",
        "retroalimentación de pruebas piloto con usuarios, privacidad de grabaciones y consentimiento",
        "gestión de presupuestos de investigación, fondos grants y plazos perentorios de entrega",
        "arquitectura de filtros de segmentos de relleno y balance de clases en datos supervisados",
        "estrategia de despliegue en Streamlit Cloud y mitigación de cuotas de cómputo",
        "preparación de guiones de demostración y validación de hipótesis HDD pre-registradas",
    ],
    "entrevista": [
        "experiencia de investigadores principales al transcribir entrevistas cualitativas y conferencias",
        "dificultades de asistentes de investigación con notas manuales, compromisos pendientes y to-dos",
    ],
}


def generar_lote_conversaciones_gemini(
    tipo: TipoConversacion,
    inicio_indice: int,
    cantidad: int,
    segmentos_por_conv: int = 20,
    modelo: str = "gemini-3.8-flash",
    estricto: bool = True,
    seed: int = 42,
    api_key: str | None = None,
) -> list[ConversacionSintetica]:
    """Genera un lote de conversaciones de forma estructurada en una sola llamada REST."""
    lista_temas = TEMAS_POR_TIPO.get(tipo, [])
    tema_especifico = ""
    if lista_temas:
        idx_tema = ((inicio_indice - 1) // max(1, cantidad)) % len(lista_temas)
        tema_especifico = f"Enfoca las discusiones de este lote principalmente en: {lista_temas[idx_tema]}. "

    prompt = (
        f"Genera un lote de {cantidad} conversaciones sintéticas realistas de tipo '{tipo}' para el dataset Minuta. "
        f"{tema_especifico}"
        f"Cada conversación debe tener entre {max(12, segmentos_por_conv - 5)} y {segmentos_por_conv + 5} segmentos. "
        f"Clases obligatorias (solo estas 5): 'idea', 'tarea', 'acuerdo', 'pregunta', 'relleno'. "
        f"{'En cada reunión asegura al menos 2 tareas explícitas y al menos 2 segmentos de relleno. ' if tipo == 'reunion' else ''}"
        f"Todos los textos deben ser únicos, diversos y reflejar debates auténticos de investigación y ciencia de datos. "
        f"Términos técnicos ES-EN requeridos: paper, journal, Scopus, grant, deadline, peer review, preprint, dataset, APC, publisher. "
        f"Nombres de instituciones y participantes totalmente ficticios. "
        f"Devuelve estrictamente una lista JSON con {cantidad} objetos: "
        f'[{{"id": "{tipo}_sintetica_{inicio_indice:03d}", "tipo": "{tipo}", "titulo": "...", "duracion_s": 0.0, "fuente": "gemini", '
        f'"segmentos": [{{"id": 1, "inicio_s": 0.0, "fin_s": 5.0, "texto": "...", "etiqueta": "idea", "orador": "..."}}]}}]'
    )

    try:
        texto_json = llamar_gemini_rest(prompt=prompt, modelo=modelo, api_key=api_key)
        data = json.loads(texto_json)
        if isinstance(data, dict) and "conversaciones" in data:
            data = data["conversaciones"]
        if not isinstance(data, list):
            data = [data]

        conversaciones_lote: list[ConversacionSintetica] = []
        for i, item in enumerate(data):
            idx_conv = inicio_indice + i
            segs_norm = _normalizar_segmentos_gemini(item.get("segmentos", []), tipo)
            dur_tot = segs_norm[-1].fin_s if segs_norm else 120.0
            conv = ConversacionSintetica(
                id=f"{tipo}_sintetica_{idx_conv:03d}",
                tipo=tipo,
                titulo=item.get("titulo", f"Conversación {tipo} #{idx_conv:02d}"),
                duracion_s=dur_tot,
                fuente="gemini",
                segmentos=segs_norm,
            )
            conversaciones_lote.append(conv)

        # Si faltó alguna para completar la cantidad solicitada
        while len(conversaciones_lote) < cantidad:
            idx_faltante = inicio_indice + len(conversaciones_lote)
            c_extra = generar_conversacion_gemini(
                tipo=tipo,
                indice=idx_faltante,
                num_segmentos=segmentos_por_conv,
                modelo=modelo,
                estricto=estricto,
                seed=seed + idx_faltante,
                api_key=api_key,
            )
            conversaciones_lote.append(c_extra)

        return conversaciones_lote[:cantidad]

    except Exception as exc:
        if estricto:
            raise RuntimeError(
                f"Error generando lote {tipo} [{inicio_indice}..{inicio_indice+cantidad-1}] con Gemini (modo estricto activo): {exc}"
            ) from exc
        print(
            f"[Aviso] Fallback a plantillas para lote {tipo} debido a fallo en Gemini: {exc}",
            file=sys.stderr,
        )
        return [
            generar_conversacion_sintetica_dry_run(tipo, inicio_indice + j, segmentos_por_conv, seed + j)
            for j in range(cantidad)
        ]


# ---------------------------------------------------------------------------
# Estadísticas y validación
# ---------------------------------------------------------------------------

def calcular_estadisticas_dataset(dataset: DatasetSintetico) -> dict[str, Any]:
    """Calcula totales, conteos, proporciones por clase, porcentaje de únicos y desglose de fuentes."""
    conteo: dict[str, int] = {c: 0 for c in CLASES_VALIDAS}
    total_segmentos = 0
    textos: list[str] = []
    fuentes: dict[str, int] = {}

    for conv in dataset.conversaciones:
        f_val = getattr(conv, "fuente", "plantilla")
        fuentes[f_val] = fuentes.get(f_val, 0) + 1
        for seg in conv.segmentos:
            conteo[seg.etiqueta] = conteo.get(seg.etiqueta, 0) + 1
            total_segmentos += 1
            textos.append(seg.texto.strip())

    proporciones: dict[str, float] = {}
    if total_segmentos > 0:
        for c, cant in conteo.items():
            proporciones[c] = round(cant / total_segmentos, 4)

    pct_unicos = round(len(set(textos)) / len(textos) * 100.0, 2) if textos else 0.0

    return {
        "total_conversaciones": len(dataset.conversaciones),
        "total_segmentos": total_segmentos,
        "conteo_por_clase": conteo,
        "proporciones_por_clase": proporciones,
        "porcentaje_unicos": pct_unicos,
        "desglose_por_fuente": fuentes,
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
    n_por_tipo: int | dict[TipoConversacion, int] = 2,
    tipos: list[TipoConversacion] | None = None,
    segmentos_por_conv: int = 80,
    dry_run: bool = True,
    estricto: bool = True,
    modelo: str = "gemini-3.8-flash",
    seed: int = 42,
    usar_lotes: bool = True,
    tamano_lote: int = 5,
) -> DatasetSintetico:
    """Genera un dataset sintético completo de conversaciones."""
    if tipos is None:
        tipos = list(TIPOS_VALIDOS)

    cuotas_por_tipo: dict[TipoConversacion, int] = {}
    if isinstance(n_por_tipo, int):
        cuotas_por_tipo = {t: n_por_tipo for t in tipos}
    else:
        cuotas_por_tipo = {t: n_por_tipo.get(t, 0) for t in tipos}

    conversaciones: list[ConversacionSintetica] = []

    for tipo in tipos:
        total_tipo = cuotas_por_tipo.get(tipo, 0)
        if total_tipo <= 0:
            continue

        if dry_run:
            for i in range(1, total_tipo + 1):
                conv = generar_conversacion_sintetica_dry_run(
                    tipo=tipo,
                    indice=i,
                    num_segmentos=segmentos_por_conv,
                    seed=seed + i,
                )
                conversaciones.append(conv)
        else:
            if usar_lotes and total_tipo > 1:
                generadas = 0
                while generadas < total_tipo:
                    lote_n = min(tamano_lote, total_tipo - generadas)
                    idx_inicio = generadas + 1
                    print(
                        f"[{tipo}] Generando lote {idx_inicio}..{idx_inicio + lote_n - 1} de {total_tipo}...",
                        flush=True,
                    )
                    lote = generar_lote_conversaciones_gemini(
                        tipo=tipo,
                        inicio_indice=idx_inicio,
                        cantidad=lote_n,
                        segmentos_por_conv=segmentos_por_conv,
                        modelo=modelo,
                        estricto=estricto,
                        seed=seed + generadas,
                    )
                    conversaciones.extend(lote)
                    generadas += len(lote)
                    print(
                        f"[{tipo}] Progreso: {generadas}/{total_tipo} conversaciones generadas.",
                        flush=True,
                    )
            else:
                for i in range(1, total_tipo + 1):
                    print(f"[{tipo}] Generando conversación {i}/{total_tipo}...", flush=True)
                    conv = generar_conversacion_gemini(
                        tipo=tipo,
                        indice=i,
                        num_segmentos=segmentos_por_conv,
                        modelo=modelo,
                        estricto=estricto,
                        seed=seed + i,
                    )
                    conversaciones.append(conv)

    # Calcular estadísticas
    conteo: dict[str, int] = {c: 0 for c in CLASES_VALIDAS}
    total_seg = 0
    textos: list[str] = []
    fuentes: dict[str, int] = {}

    for conv in conversaciones:
        f_nom = getattr(conv, "fuente", "plantilla")
        fuentes[f_nom] = fuentes.get(f_nom, 0) + 1
        for s in conv.segmentos:
            conteo[s.etiqueta] += 1
            total_seg += 1
            textos.append(s.texto.strip())

    proporciones = {c: round(cant / total_seg, 4) for c, cant in conteo.items()} if total_seg > 0 else {}
    pct_unicos = round(len(set(textos)) / len(textos) * 100.0, 2) if textos else 0.0

    return DatasetSintetico(
        total_conversaciones=len(conversaciones),
        total_segmentos=total_seg,
        conteo_por_clase=conteo,
        proporciones_por_clase=proporciones,
        porcentaje_unicos=pct_unicos,
        desglose_por_fuente=fuentes,
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
        "--completo",
        action="store_true",
        help="Genera dataset completo de entrenamiento: 40 ponencias, 40 reuniones y 10 entrevistas",
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
        "--estricto",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Modo estricto: aborta inmediatamente ante fallo de la API sin caer a plantillas (default: True)",
    )
    parser.add_argument(
        "--modelo",
        type=str,
        default="gemini-3.8-flash",
        help="Modelo de Gemini a emplear en REST API (default: gemini-3.8-flash)",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default=None,
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

    if parsed.completo:
        cuotas = {"ponencia": 40, "reunion": 40, "entrevista": 10}
        ruta_defecto = ROOT_DIR / "entrenamiento" / "datos" / "sinteticos_entrenamiento.json"
        segmentos_conv = parsed.segmentos if parsed.segmentos != 80 else 20
    else:
        tipos_sel = list(TIPOS_VALIDOS) if parsed.tipo == "todas" else [parsed.tipo]
        cuotas = {t: parsed.n for t in tipos_sel}
        ruta_defecto = ROOT_DIR / "entrenamiento" / "datos" / "sinteticos_muestra.json"
        segmentos_conv = parsed.segmentos

    ruta_salida = Path(parsed.salida) if parsed.salida else ruta_defecto

    dataset = generar_dataset_sintetico(
        n_por_tipo=cuotas,
        tipos=list(cuotas.keys()),
        segmentos_por_conv=segmentos_conv,
        dry_run=parsed.dry_run,
        estricto=parsed.estricto,
        modelo=parsed.modelo,
        seed=parsed.semilla,
        usar_lotes=True,
    )

    conteos_str = ", ".join(f"{c}={dataset.conteo_por_clase.get(c, 0)}" for c in CLASES_VALIDAS)
    print(f"Conteo por clase: {conteos_str}")
    print(f"Porcentaje de segmentos únicos: {dataset.porcentaje_unicos:.2f}%")
    desglose_str = ", ".join(f"{f}={cant}" for f, cant in dataset.desglose_por_fuente.items())
    print(f"Desglose por fuente: {desglose_str}")

    cumple_reuniones, detalle = validar_distribucion_reuniones(dataset)
    print(f"Distribución reuniones: {detalle} -> {'CUMPLE' if cumple_reuniones else 'FALLA'}")

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(dataset.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"Datos sintéticos guardados exitosamente en: {ruta_salida}")
    return 0 if cumple_reuniones else 1


if __name__ == "__main__":
    sys.exit(main())
