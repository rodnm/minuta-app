"""Detector de intención y filtrado de segmentos para Minuta.

Aplica mmBERT-small para clasificar segmentos de audio en:
- idea
- tarea
- acuerdo
- pregunta
- relleno

Permite:
1. Filtrar segmentos de relleno para reducir tokens y costos en el LLM (H5a, H5b).
2. Extraer candidatos a tareas y acuerdos para alimentar listas to-do.
3. Fallback defensivo a solo_llm si el modelo no está disponible.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Sequence

from minuta.esquemas import Segmento, Transcripcion

logger = logging.getLogger(__name__)

CLASES_DETECTOR: list[str] = ["idea", "tarea", "acuerdo", "pregunta", "relleno"]
MODELO_DETECTOR_DEFAULT: str = "rodnm/minuta-detector-mmbert-small"


class DetectorSegmentos:
    """Detector y clasificador de intención para segmentos transcritos."""

    def __init__(
        self,
        modelo_id: str | Path | None = None,
        clasificador: Any = None,
        device: str | int | None = None,
    ) -> None:
        self.modelo_id = str(modelo_id) if modelo_id is not None else MODELO_DETECTOR_DEFAULT
        self._clasificador = clasificador
        self._disponible = False

        if self._clasificador is not None:
            self._disponible = True
        else:
            self._cargar_modelo(device=device)

    def _cargar_modelo(self, device: str | int | None = None) -> None:
        """Carga defensiva del modelo usando transformers.pipeline."""
        try:
            from transformers import pipeline  # type: ignore

            p = Path(self.modelo_id)
            # Si es una ruta local y no existe o no tiene config.json, evitar llamada que falle
            if p.is_dir() and not (p / "config.json").exists():
                self._disponible = False
                return

            dev = device if device is not None else -1
            self._clasificador = pipeline(
                "text-classification",
                model=self.modelo_id,
                device=dev,
            )
            self._disponible = True
        except Exception as exc:
            logger.warning(
                "No se pudo cargar el modelo del detector en '%s': %s. Operando en modo fallback.",
                self.modelo_id,
                exc,
            )
            self._clasificador = None
            self._disponible = False

    @property
    def disponible(self) -> bool:
        """Indica si el clasificador está listo para inferir."""
        return self._disponible

    def clasificar(self, segmentos: Sequence[Segmento]) -> list[str]:
        """Clasifica una secuencia de segmentos y devuelve sus etiquetas predichas."""
        if not self._disponible or self._clasificador is None:
            raise RuntimeError("El detector no está disponible o no se pudo cargar el modelo.")

        if not segmentos:
            return []

        textos = [s.texto for s in segmentos]
        try:
            salidas = self._clasificador(textos)
        except TypeError:
            salidas = [self._clasificador(t) for t in textos]

        etiquetas: list[str] = []
        for item in salidas:
            if isinstance(item, dict):
                etiquetas.append(item.get("label", "idea"))
            elif isinstance(item, str):
                etiquetas.append(item)
            elif isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                etiquetas.append(item[0].get("label", "idea"))
            else:
                etiquetas.append(str(item))

        return etiquetas

    def filtrar_relleno(
        self,
        segmentos: Sequence[Segmento],
        etiquetas: Sequence[str] | None = None,
    ) -> tuple[list[Segmento], int]:
        """Filtra y descarta los segmentos clasificados como 'relleno'.

        Retorna la tupla (segmentos_retenidos, cantidad_descartados).
        """
        if not segmentos:
            return [], 0

        if etiquetas is None:
            if self.disponible:
                etiquetas = self.clasificar(segmentos)
            else:
                return list(segmentos), 0

        if len(etiquetas) != len(segmentos):
            raise ValueError(
                f"La cantidad de etiquetas ({len(etiquetas)}) debe coincidir con la de segmentos ({len(segmentos)})"
            )

        retenidos: list[Segmento] = []
        descartados: int = 0

        for seg, lbl in zip(segmentos, etiquetas):
            if lbl == "relleno":
                descartados += 1
            else:
                retenidos.append(seg)

        return retenidos, descartados

    def extraer_candidatos_todo(
        self,
        segmentos: Sequence[Segmento],
        etiquetas: Sequence[str] | None = None,
    ) -> list[Segmento]:
        """Extrae los segmentos correspondientes a 'tarea' o 'acuerdo'."""
        if not segmentos:
            return []

        if etiquetas is None:
            if self.disponible:
                etiquetas = self.clasificar(segmentos)
            else:
                return []

        candidatos: list[Segmento] = []
        for seg, lbl in zip(segmentos, etiquetas):
            if lbl in ("tarea", "acuerdo"):
                candidatos.append(seg)

        return candidatos

    def procesar_transcripcion(
        self,
        transcripcion: Transcripcion,
        tipo_plantilla: str = "ponencia",
    ) -> dict[str, Any]:
        """Ejecuta clasificación, filtrado de relleno y extracción de candidatos to-do."""
        total_orig = len(transcripcion.segmentos)

        if not self.disponible or not transcripcion.segmentos:
            return {
                "modo_efectivo": "solo_llm",
                "segmentos_procesados": list(transcripcion.segmentos),
                "relleno_descartado": 0,
                "candidatos_todo": [],
                "total_original": total_orig,
                "total_retenido": total_orig,
                "ahorro_segmentos_pct": 0.0,
            }

        etiquetas = self.clasificar(transcripcion.segmentos)
        retenidos, desc = self.filtrar_relleno(transcripcion.segmentos, etiquetas=etiquetas)
        candidatos = self.extraer_candidatos_todo(transcripcion.segmentos, etiquetas=etiquetas)

        ahorro_pct = round((desc / total_orig) * 100, 2) if total_orig > 0 else 0.0

        return {
            "modo_efectivo": "detector",
            "segmentos_procesados": retenidos,
            "relleno_descartado": desc,
            "candidatos_todo": candidatos,
            "total_original": total_orig,
            "total_retenido": len(retenidos),
            "ahorro_segmentos_pct": ahorro_pct,
        }
