"""Proveedores de LLM con salida estructurada Pydantic v2 para Minuta.

Implementa la interfaz abstracta ProveedorLLM y los adaptadores para:
- ProveedorGemini: API REST de Google Gemini v1beta con structured outputs.
- ProveedorOllama: API local de Ollama con formato JSON schema y supresión de thinking.
- ProveedorMock: proveedor determinista para tests unitarios y CI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar
import urllib.error
import urllib.request

import requests
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class ErrorProveedorLLM(Exception):
    """Excepción base para errores durante la generación con proveedores LLM."""

    pass


def _obtener_gemini_api_key() -> str | None:
    """Busca la clave GEMINI_API_KEY en variables de entorno o en el archivo .env."""
    key = os.getenv("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip().strip('"').strip("'")

    # Búsqueda en .env local
    ruta_env = Path(".env")
    if ruta_env.exists():
        try:
            for linea in ruta_env.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if linea.startswith("GEMINI_API_KEY="):
                    val = linea.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
        except Exception:
            pass

    return None


def _limpiar_texto_json(raw: str) -> str:
    """Extrae el contenido JSON limpio eliminando etiquetas de pensamiento y markdown."""
    texto = raw.strip()

    # Eliminar bloques de pensamiento <think>...</think>
    texto = re.sub(r"<think>[\s\S]*?</think>", "", texto, flags=re.IGNORECASE).strip()

    # Eliminar bloques de código markdown ```json ... ```
    patron_md = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", texto, flags=re.IGNORECASE)
    if patron_md:
        texto = patron_md.group(1).strip()

    # Si no inicia con { o [, intentar localizar el primer objeto JSON
    if not (texto.startswith("{") or texto.startswith("[")):
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            texto = texto[inicio : fin + 1]

    return texto


class ProveedorLLM(ABC):
    """Interfaz abstracta para proveedores de modelos de lenguaje con salida estructurada."""

    @abstractmethod
    def generar_estructurado(self, prompt: str, esquema: type[T]) -> T:
        """Genera una respuesta estructurada validada según el esquema Pydantic."""
        pass


class ProveedorGemini(ProveedorLLM):
    """Proveedor para la API REST de Google Gemini (v1beta) con salida estructurada Pydantic."""

    def __init__(
        self,
        api_key: str | None = None,
        modelo: str = "gemini-3.8-flash",
        modelo_fallback: str = "gemini-2.5-flash",
        timeout: float = 60.0,
        max_reintentos: int = 2,
    ) -> None:
        self.api_key = api_key or _obtener_gemini_api_key()
        if not self.api_key:
            raise ErrorProveedorLLM(
                "GEMINI_API_KEY no configurada. Provea api_key o configure la variable de entorno."
            )
        self.modelo = modelo
        self.modelo_fallback = modelo_fallback
        self.timeout = timeout
        self.max_reintentos = max_reintentos

    def generar_estructurado(self, prompt: str, esquema: type[T]) -> T:
        """Invoca la API REST de Gemini y valida la respuesta contra el esquema Pydantic."""
        modelos_a_probar = [self.modelo]
        if self.modelo_fallback and self.modelo_fallback not in modelos_a_probar:
            modelos_a_probar.append(self.modelo_fallback)

        schema_json = esquema.model_json_schema()

        ultimo_error: str | None = None

        for mod in modelos_a_probar:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                    "responseSchema": schema_json,
                },
            }

            for intento in range(1, self.max_reintentos + 1):
                try:
                    resp = requests.post(url, json=payload, timeout=self.timeout)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            raise ErrorProveedorLLM(f"Respuesta de Gemini sin candidatos en modelo {mod}")

                        parts = candidates[0].get("content", {}).get("parts", [])
                        if not parts or "text" not in parts[0]:
                            raise ErrorProveedorLLM(f"Respuesta de Gemini sin texto en modelo {mod}")

                        texto_crudo = parts[0]["text"]
                        texto_limpio = _limpiar_texto_json(texto_crudo)
                        return esquema.model_validate_json(texto_limpio)

                    if resp.status_code in (429, 503):
                        ultimo_error = f"HTTP {resp.status_code} ({mod}): demanda alta o límite excedido."
                        time.sleep(1.0 * intento)
                        continue

                    if resp.status_code == 404:
                        ultimo_error = f"HTTP 404 ({mod}): modelo no disponible en endpoint v1beta."
                        break

                    ultimo_error = f"HTTP {resp.status_code} ({mod}): {resp.text[:200]}"
                    break

                except (requests.RequestException, ValidationError) as exc:
                    ultimo_error = f"Excepción en {mod} intento {intento}: {exc}"
                    if intento < self.max_reintentos:
                        time.sleep(1.0 * intento)

        raise ErrorProveedorLLM(f"Fallo en llamada a Gemini API: {ultimo_error}")


class ProveedorOllama(ProveedorLLM):
    """Proveedor para la API local de Ollama (/api/generate) con JSON Schema y temperatura 0."""

    def __init__(
        self,
        host: str | None = None,
        modelo: str = "qwen3:4b",
        timeout: float = 120.0,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.modelo = modelo
        self.timeout = timeout

    def generar_estructurado(self, prompt: str, esquema: type[T]) -> T:
        """Invoca el endpoint /api/generate de Ollama con format=esquema.model_json_schema()."""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.modelo,
            "prompt": prompt,
            "format": esquema.model_json_schema(),
            "stream": False,
            "options": {
                "temperature": 0.0,
                "think": False,
            },
            "think": False,
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                raise ErrorProveedorLLM(
                    f"Ollama retornó código de error HTTP {resp.status_code}: {resp.text[:200]}"
                )

            data = resp.json()
            texto_respuesta = data.get("response", "")
            texto_limpio = _limpiar_texto_json(texto_respuesta)
            return esquema.model_validate_json(texto_limpio)

        except requests.RequestException as exc:
            raise ErrorProveedorLLM(f"Fallo de conexión con Ollama en {self.host}: {exc}") from exc
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ErrorProveedorLLM(f"Error al validar respuesta JSON de Ollama contra {esquema.__name__}: {exc}") from exc


class ProveedorMock(ProveedorLLM):
    """Proveedor simulado y determinista para pruebas unitarias y entornos sin conexión."""

    def __init__(
        self,
        respuestas: list[Any] | dict[Any, Any] | Callable[[str, type[BaseModel]], Any] | Any = None,
    ) -> None:
        if isinstance(respuestas, list):
            self._respuestas = list(respuestas)
        elif respuestas is not None:
            self._respuestas = respuestas
        else:
            self._respuestas = []

        self.llamadas: list[tuple[str, type[BaseModel]]] = []

    def generar_estructurado(self, prompt: str, esquema: type[T]) -> T:
        """Retorna una respuesta simulada determinista y registra los parámetros de llamada."""
        self.llamadas.append((prompt, esquema))

        if callable(self._respuestas):
            valor = self._respuestas(prompt, esquema)
        elif isinstance(self._respuestas, list):
            if not self._respuestas:
                raise ErrorProveedorLLM("No hay más respuestas simuladas disponibles en ProveedorMock")
            valor = self._respuestas.pop(0)
        elif isinstance(self._respuestas, dict):
            valor = self._respuestas.get(esquema, self._respuestas.get(prompt))
            if valor is None:
                raise ErrorProveedorLLM(f"No se encontró respuesta para {esquema.__name__} en ProveedorMock")
        else:
            valor = self._respuestas

        if isinstance(valor, esquema):
            return valor
        if isinstance(valor, str):
            return esquema.model_validate_json(_limpiar_texto_json(valor))
        if isinstance(valor, dict):
            return esquema.model_validate(valor)
        if isinstance(valor, BaseModel):
            return esquema.model_validate(valor.model_dump())

        raise ErrorProveedorLLM(
            f"El valor simulado de tipo {type(valor).__name__} no puede convertirse al esquema {esquema.__name__}"
        )
