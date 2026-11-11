"""Pruebas de la llamada REST a Gemini del generador de sintéticos (T50, L51 A2).

Las llamadas HTTP se simulan: ninguna prueba contacta la API real.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from entrenamiento.generar_sinteticos import llamar_gemini_rest

CLAVE_FALSA = "CLAVE-FALSA-sinteticos-987654321"


@pytest.fixture
def posts(monkeypatch):
    registro: dict[str, Any] = {"posts": [], "respuestas": []}

    def post_falso(url, json=None, headers=None, timeout=None, **kwargs):
        registro["posts"].append({"url": url, "headers": headers or {}})
        respuesta = registro["respuestas"].pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr("entrenamiento.generar_sinteticos.requests.post", post_falso)
    monkeypatch.setattr("entrenamiento.generar_sinteticos.time.sleep", lambda s: None)
    return registro


class _RespuestaFalsa:
    status_code = 200
    text = ""

    def json(self) -> dict[str, Any]:
        return {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]}


def test_llamar_gemini_rest_clave_en_cabecera_y_ausente_de_url_y_errores(posts):
    url = "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent"
    posts["respuestas"] = [requests.ConnectionError(f"Max retries exceeded with url: {url}") for _ in range(8)]

    with pytest.raises(RuntimeError) as info:
        llamar_gemini_rest("prompt", api_key=CLAVE_FALSA, max_reintentos=1)

    assert CLAVE_FALSA not in str(info.value)
    assert posts["posts"]
    for post in posts["posts"]:
        assert post["headers"].get("x-goog-api-key") == CLAVE_FALSA
        assert CLAVE_FALSA not in post["url"]
        assert "key=" not in post["url"]


def test_llamar_gemini_rest_sigue_devolviendo_el_texto(posts):
    posts["respuestas"] = [_RespuestaFalsa()]

    texto = llamar_gemini_rest("prompt", modelo="gemini-3.8-flash", api_key=CLAVE_FALSA)

    assert texto == '{"ok": true}'
    assert len(posts["posts"]) == 1
    assert "/models/gemini-3.8-flash:generateContent" in posts["posts"][0]["url"]
