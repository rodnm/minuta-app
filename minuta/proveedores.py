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


URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

# Campos que calcula Minuta y que no se le piden al modelo.
CAMPOS_INTERNOS = ("descartados", "modo")


def _esquema_para_modelo(esquema: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema que se envía a Gemini: el del modelo Pydantic sin los campos internos."""
    schema = esquema.model_json_schema()
    propiedades = schema.get("properties", {})
    for campo in CAMPOS_INTERNOS:
        propiedades.pop(campo, None)
    if "required" in schema:
        schema["required"] = [c for c in schema["required"] if c not in CAMPOS_INTERNOS]
    return schema


def _texto_de_respuesta_gemini(datos: dict[str, Any]) -> str | None:
    """Une las partes de texto del primer candidato, sin las partes de razonamiento."""
    candidatos = datos.get("candidates") or []
    if not candidatos:
        return None
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    textos = [p["text"] for p in partes if "text" in p and not p.get("thought")]
    return "".join(textos) if textos else None


class ProveedorGemini(ProveedorLLM):
    """Proveedor para la API REST de Google Gemini (v1beta) con salida estructurada Pydantic.

    La clave viaja en la cabecera x-goog-api-key, nunca en la URL. Ante 429 o 503 reintenta una
    vez con espera y luego pasa al modelo de respaldo; también pasa al respaldo, sin reintentar,
    si la respuesta no trae candidatos, si vence el timeout o ante cualquier otro error HTTP. Tras cada llamada exitosa expone el modelo
    que respondió (ultimo_modelo) y su usageMetadata (ultimo_uso).
    """

    def __init__(
        self,
        api_key: str | None = None,
        modelo: str = "gemini-3.8-flash",
        modelo_fallback: str = "gemini-3.6-flash",
        timeout: float = 180.0,
        max_reintentos: int = 2,
        espera_reintento_s: float = 2.0,
    ) -> None:
        self.api_key = api_key or _obtener_gemini_api_key()
        if not self.api_key:
            raise ErrorProveedorLLM(
                "GEMINI_API_KEY no configurada. Provea api_key o configure la variable de entorno."
            )
        self.modelo = modelo
        self.modelo_fallback = modelo_fallback
        self.timeout = timeout
        self.max_reintentos = max(1, max_reintentos)
        self.espera_reintento_s = espera_reintento_s
        self.ultimo_modelo: str | None = None
        self.ultimo_uso: dict[str, Any] | None = None

    def _ocultar_clave(self, texto: str) -> str:
        return texto.replace(self.api_key, "***") if self.api_key else texto

    def generar_estructurado(self, prompt: str, esquema: type[T]) -> T:
        """Invoca la API REST de Gemini y valida la respuesta contra el esquema Pydantic."""
        modelos_a_probar = [self.modelo]
        if self.modelo_fallback and self.modelo_fallback not in modelos_a_probar:
            modelos_a_probar.append(self.modelo_fallback)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "responseJsonSchema": _esquema_para_modelo(esquema),
            },
        }
        cabeceras = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

        errores: list[str] = []

        for mod in modelos_a_probar:
            url = URL_GEMINI.format(modelo=mod)
            error_modelo = "sin intentos"

            for intento in range(1, self.max_reintentos + 1):
                hay_reintento = intento < self.max_reintentos
                try:
                    resp = requests.post(url, json=payload, headers=cabeceras, timeout=self.timeout)
                except requests.Timeout:
                    # El servidor pudo procesar (y cobrar) la petición: no se repite, se pasa al respaldo
                    error_modelo = f"sin respuesta en {self.timeout:.0f} s (timeout)"
                    break
                except requests.RequestException as exc:
                    error_modelo = f"error de conexión: {exc}"
                    if hay_reintento:
                        time.sleep(self.espera_reintento_s * intento)
                        continue
                    break

                if resp.status_code == 200:
                    datos = resp.json()
                    texto_crudo = _texto_de_respuesta_gemini(datos)
                    if texto_crudo is None:
                        motivo = (datos.get("promptFeedback") or {}).get("blockReason")
                        error_modelo = "respuesta sin candidatos" + (f" ({motivo})" if motivo else "")
                        break
                    try:
                        resultado = esquema.model_validate_json(_limpiar_texto_json(texto_crudo))
                    except ValidationError as exc:
                        error_modelo = f"JSON no válido contra {esquema.__name__}: {exc}"
                        if hay_reintento:
                            time.sleep(self.espera_reintento_s * intento)
                            continue
                        break
                    self.ultimo_modelo = mod
                    self.ultimo_uso = datos.get("usageMetadata")
                    return resultado

                error_modelo = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code in (429, 503) and hay_reintento:
                    time.sleep(self.espera_reintento_s * intento)
                    continue
                break

            errores.append(f"{mod}: {error_modelo}")

        raise ErrorProveedorLLM(self._ocultar_clave("Fallo en llamada a Gemini API: " + " | ".join(errores)))


class ProveedorOllama(ProveedorLLM):
    """Proveedor para la API local de Ollama (/api/generate) con JSON Schema y temperatura 0.

    El timeout por defecto es de 600 s (un bloque de 10 min en CPU puede tardar varios minutos)
    y se configura con el parámetro timeout o la variable de entorno OLLAMA_TIMEOUT.
    """

    TIMEOUT_POR_DEFECTO_S = 600.0

    def __init__(
        self,
        host: str | None = None,
        modelo: str = "qwen3:4b",
        timeout: float | None = None,
        num_ctx: int = 8192,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.modelo = modelo
        if timeout is None:
            try:
                timeout = float(os.getenv("OLLAMA_TIMEOUT", self.TIMEOUT_POR_DEFECTO_S))
            except ValueError:
                timeout = self.TIMEOUT_POR_DEFECTO_S
        self.timeout = float(timeout)
        self.num_ctx = num_ctx

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
                "num_ctx": self.num_ctx,
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
