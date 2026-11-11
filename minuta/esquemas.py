"""Contrato de datos Pydantic v2 para Minuta.

Define los esquemas del sistema: transcripción, evidencias literales,
árbol del mapa mental y resultados de las 3 plantillas (Ponencia, Reunión, Entrevista).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class Segmento(BaseModel):
    """Segmento de audio transcrito con marca temporal."""

    id: str | int
    inicio_s: float = Field(..., ge=0.0, description="Tiempo de inicio en segundos")
    fin_s: float = Field(..., description="Tiempo de fin en segundos")
    texto: str = Field(..., description="Texto transcrito en este segmento")

    @model_validator(mode="after")
    def _validar_intervalo(self) -> Segmento:
        if self.fin_s < self.inicio_s:
            raise ValueError(f"fin_s ({self.fin_s}) no puede ser menor que inicio_s ({self.inicio_s})")
        return self


class Transcripcion(BaseModel):
    """Transcripción completa de un audio dividida en segmentos."""

    audio_id: str
    duracion_s: float = Field(..., ge=0.0)
    modelo: str
    glosario: list[str] = Field(default_factory=list)
    segmentos: list[Segmento]


class Evidencia(BaseModel):
    """Cita textual exacta que respalda una afirmación o nodo."""

    segmento_ids: list[str | int] = Field(..., description="IDs de los segmentos donde se encuentra la cita")
    inicio_s: float = Field(..., ge=0.0, description="Tiempo de inicio de la cita en segundos")
    cita: str = Field(..., description="Texto textual exacto extraído de los segmentos")

    @field_validator("cita")
    @classmethod
    def _validar_cita_no_vacia(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La cita de evidencia no puede estar vacía")
        return v

    @field_validator("segmento_ids")
    @classmethod
    def _validar_segmento_ids_no_vacio(cls, v: list[str | int]) -> list[str | int]:
        if not v:
            raise ValueError("Debe asociarse al menos un segmento_id a la evidencia")
        return v


# Longitud mínima de una cita, medida tras normalizarla. Descarta citas triviales como "de",
# que aparecen en cualquier transcripción. La cita más corta de data/fixtures/ y data/demo/
# tiene 6 palabras y 37 caracteres, así que todas siguen validando.
MIN_PALABRAS_CITA = 3
MIN_CARACTERES_CITA = 12

_COMILLAS_TIPOGRAFICAS = str.maketrans(
    {
        "“": '"',  # “
        "”": '"',  # ”
        "„": '"',  # „
        "‟": '"',  # ‟
        "«": '"',  # «
        "»": '"',  # »
        "‘": "'",  # ‘
        "’": "'",  # ’
        "‚": "'",  # ‚
        "‛": "'",  # ‛
    }
)


def normalizar_texto_cita(texto: str) -> str:
    """Normaliza un texto para comparar citas: NFC, comillas rectas y espacios colapsados."""
    texto = unicodedata.normalize("NFC", texto).translate(_COMILLAS_TIPOGRAFICAS)
    return re.sub(r"\s+", " ", texto).strip()


def localizar_cita_literal(cita: str, segmentos: list[Segmento]) -> list[Segmento]:
    """Devuelve los segmentos que abarca la primera aparición literal de la cita.

    Compara ambos lados normalizados (NFC, espacios múltiples y comillas tipográficas).
    Busca primero en cada segmento y luego en la unión de segmentos separados por un espacio;
    nunca une segmentos sin espacio. Devuelve una lista vacía si la cita no aparece o si es
    más corta que MIN_PALABRAS_CITA palabras o MIN_CARACTERES_CITA caracteres.
    """
    if not cita or not segmentos:
        return []

    cita_norm = normalizar_texto_cita(cita)
    if len(cita_norm) < MIN_CARACTERES_CITA or len(cita_norm.split(" ")) < MIN_PALABRAS_CITA:
        return []

    textos = [normalizar_texto_cita(s.texto) for s in segmentos]

    # 1. Dentro de un solo segmento
    for seg, texto in zip(segmentos, textos):
        if cita_norm in texto:
            return [seg]

    # 2. Entre segmentos consecutivos unidos por un espacio
    unido = ""
    tramos: list[tuple[int, int, Segmento]] = []
    for seg, texto in zip(segmentos, textos):
        if not texto:
            continue
        if unido:
            unido += " "
        inicio = len(unido)
        unido += texto
        tramos.append((inicio, len(unido), seg))

    pos = unido.find(cita_norm)
    if pos < 0:
        return []
    fin = pos + len(cita_norm)
    return [seg for inicio, final, seg in tramos if inicio < fin and final > pos]


def validar_evidencia_literal(cita: str, segmentos: list[Segmento]) -> bool:
    """Verifica si la cita es una subcadena literal de los segmentos dados.

    Ver localizar_cita_literal para la normalización y la longitud mínima.
    """
    return bool(localizar_cita_literal(cita, segmentos))


class NodoMapa(BaseModel):
    """Nodo dentro del árbol de mapa mental.

    La raíz tiene evidencia=None; los nodos internos y hojas llevan evidencia.
    """

    id: str
    titulo: str
    resumen: str | None = None
    evidencia: Evidencia | None = None
    hijos: list[NodoMapa] = Field(default_factory=list)

    def tiempo_tag(self) -> str | None:
        """Devuelve el tag formateado [mm:ss] si el nodo posee evidencia."""
        if self.evidencia is None:
            return None
        minutos = int(self.evidencia.inicio_s // 60)
        segundos = int(self.evidencia.inicio_s % 60)
        return f"[{minutos:02d}:{segundos:02d}]"


class MapaMental(BaseModel):
    """Árbol completo de mapa mental para visualización con markmap."""

    titulo: str
    raiz: NodoMapa

    def to_markdown(self) -> str:
        """Genera el árbol en formato Markdown (#, ##, ###...) con tag [mm:ss]."""
        lineas: list[str] = []

        def _recorrer(nodo: NodoMapa, nivel: int) -> None:
            prefijo = "#" * max(1, nivel)
            tag = nodo.tiempo_tag()
            tag_str = f" {tag}" if tag else ""
            lineas.append(f"{prefijo} {nodo.titulo}{tag_str}")
            if nodo.resumen:
                lineas.append(nodo.resumen)
            for hijo in nodo.hijos:
                _recorrer(hijo, nivel + 1)

        _recorrer(self.raiz, 1)
        return "\n".join(lineas)


class Tarea(BaseModel):
    """Tarea o to-do identificado en la transcripción."""

    descripcion: str
    responsable: str | None = None
    fecha_limite: str | None = None
    evidencia: Evidencia


class Acuerdo(BaseModel):
    """Acuerdo o decisión pactada en la conversación."""

    descripcion: str
    evidencia: Evidencia


class Pendiente(BaseModel):
    """Pregunta abierta o tema pendiente de resolver."""

    descripcion: str
    evidencia: Evidencia


class Tema(BaseModel):
    """Tema o idea clave discutida en la ponencia o reunión."""

    titulo: str
    resumen: str
    evidencias: list[Evidencia] = Field(default_factory=list)


class CodigoLibro(BaseModel):
    """Definición de código o categoría temática para entrevistas."""

    codigo: str
    descripcion: str


class FragmentoCodificado(BaseModel):
    """Fragmento de entrevista clasificado bajo un código del libro."""

    codigo: str
    evidencia: Evidencia
    nota: str | None = None


class ResultadoPonencia(BaseModel):
    """Estructuración completa para plantilla de Ponencia, Clase o Charla."""

    resumen_general: str
    ideas_clave: list[Tema]
    preguntas: list[Pendiente]
    mapa: MapaMental
    descartados: int = 0
    modo: Literal["solo_llm", "detector"] = "solo_llm"


class ResultadoReunion(BaseModel):
    """Estructuración completa para plantilla de Reunión de trabajo."""

    resumen_general: str
    temas: list[Tema]
    acuerdos: list[Acuerdo]
    tareas: list[Tarea]
    pendientes: list[Pendiente]
    mapa: MapaMental
    descartados: int = 0
    modo: Literal["solo_llm", "detector"] = "solo_llm"


class ResultadoEntrevista(BaseModel):
    """Estructuración completa para plantilla de Entrevista de investigación."""

    libro: list[CodigoLibro]
    fragmentos: list[FragmentoCodificado]
    resumen_por_codigo: dict[str, str]
    mapa: MapaMental
    descartados: int = 0
    modo: Literal["solo_llm", "detector"] = "solo_llm"
