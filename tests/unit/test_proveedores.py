"""Pruebas unitarias de los proveedores LLM de Minuta (T50, L51 Unidad A: A1, A2, A3, A8).

Todas las llamadas HTTP se simulan con monkeypatch: ninguna prueba contacta la API real.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from minuta.esquemas import ResultadoReunion
from minuta.proveedores import ErrorProveedorLLM, ProveedorGemini, ProveedorOllama

FIXTURES_DIR = ROOT_DIR / "data" / "fixtures"
CLAVE_FALSA = "CLAVE-FALSA-0123456789-secreta"
USO_FALSO = {"promptTokenCount": 120, "candidatesTokenCount": 80, "thoughtsTokenCount": 40}


class _RespuestaFalsa:
    def __init__(self, status_code: int, datos: dict[str, Any] | None = None, texto: str = "") -> None:
        self.status_code = status_code
        self._datos = datos or {}
        self.text = texto or json.dumps(self._datos)

    def json(self) -> dict[str, Any]:
        return self._datos


def _respuesta_ok(texto_json: str) -> _RespuestaFalsa:
    return _RespuestaFalsa(
        200,
        {
            "candidates": [{"content": {"parts": [{"text": texto_json}]}}],
            "usageMetadata": USO_FALSO,
        },
    )


def _json_reunion_sin_campos_internos() -> str:
    datos = json.loads((FIXTURES_DIR / "resultado_reunion.json").read_text(encoding="utf-8"))
    datos.pop("descartados", None)
    datos.pop("modo", None)
    return json.dumps(datos, ensure_ascii=False)


@pytest.fixture
def llamadas(monkeypatch):
    """Registra cada requests.post y cada time.sleep; las respuestas se encolan por prueba."""
    registro: dict[str, Any] = {"posts": [], "esperas": [], "respuestas": []}

    def post_falso(url, json=None, headers=None, timeout=None, **kwargs):
        registro["posts"].append({"url": url, "json": json, "headers": headers or {}, "timeout": timeout})
        respuesta = registro["respuestas"].pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr("minuta.proveedores.requests.post", post_falso)
    monkeypatch.setattr("minuta.proveedores.time.sleep", lambda s: registro["esperas"].append(s))
    return registro


def _modelo_de(url: str) -> str:
    return url.split("/models/")[1].split(":")[0]


# ---------------------------------------------------------------------------
# A1. responseJsonSchema y sin campos internos
# ---------------------------------------------------------------------------

def test_gemini_usa_response_json_schema_sin_campos_internos(llamadas):
    llamadas["respuestas"] = [_respuesta_ok(_json_reunion_sin_campos_internos())]
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)

    resultado = proveedor.generar_estructurado("prompt de prueba", ResultadoReunion)

    config = llamadas["posts"][0]["json"]["generationConfig"]
    assert "responseSchema" not in config
    assert config["responseMimeType"] == "application/json"
    esquema = config["responseJsonSchema"]
    assert "descartados" not in esquema["properties"]
    assert "modo" not in esquema["properties"]
    assert "descartados" not in esquema.get("required", [])
    assert "modo" not in esquema.get("required", [])
    # Los campos de contenido y las definiciones anidadas siguen en el esquema
    assert {"resumen_general", "temas", "acuerdos", "tareas", "pendientes", "mapa"} <= set(esquema["properties"])
    assert "$defs" in esquema
    # La respuesta sin campos internos se valida con sus valores por defecto
    assert isinstance(resultado, ResultadoReunion)
    assert resultado.descartados == 0
    assert resultado.modo == "solo_llm"


# ---------------------------------------------------------------------------
# A2. La clave viaja en la cabecera, nunca en la URL ni en los errores
# ---------------------------------------------------------------------------

def test_gemini_clave_en_cabecera_y_ausente_de_url_y_errores(llamadas):
    def error_conexion():
        # requests incluye la URL completa en el mensaje de un ConnectionError
        url = "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent"
        return requests.ConnectionError(f"Max retries exceeded with url: {url}")

    llamadas["respuestas"] = [error_conexion() for _ in range(4)]
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)

    with pytest.raises(ErrorProveedorLLM) as info:
        proveedor.generar_estructurado("prompt", ResultadoReunion)

    assert CLAVE_FALSA not in str(info.value)
    assert llamadas["posts"], "Debe intentar al menos una llamada"
    for post in llamadas["posts"]:
        assert post["headers"].get("x-goog-api-key") == CLAVE_FALSA
        assert CLAVE_FALSA not in post["url"]
        assert "key=" not in post["url"]


# ---------------------------------------------------------------------------
# A3. Modelo de respaldo vigente, 503 con reintento y error final con ambos modelos
# ---------------------------------------------------------------------------

def test_gemini_respaldo_por_defecto_es_modelo_vigente():
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)
    assert proveedor.modelo == "gemini-3.8-flash"
    assert proveedor.modelo_fallback == "gemini-3.6-flash"


def test_gemini_503_reintenta_una_vez_con_espera_y_cae_al_respaldo(llamadas):
    llamadas["respuestas"] = [
        _RespuestaFalsa(503, texto="UNAVAILABLE"),
        _RespuestaFalsa(503, texto="UNAVAILABLE"),
        _respuesta_ok(_json_reunion_sin_campos_internos()),
    ]
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)

    resultado = proveedor.generar_estructurado("prompt", ResultadoReunion)

    modelos = [_modelo_de(p["url"]) for p in llamadas["posts"]]
    assert modelos == ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.6-flash"]
    assert len(llamadas["esperas"]) == 1 and llamadas["esperas"][0] > 0
    assert isinstance(resultado, ResultadoReunion)
    # El proveedor expone el modelo que respondió y su usageMetadata
    assert proveedor.ultimo_modelo == "gemini-3.6-flash"
    assert proveedor.ultimo_uso == USO_FALSO


def test_gemini_sin_candidatos_cae_al_respaldo(llamadas):
    llamadas["respuestas"] = [
        _RespuestaFalsa(200, {"candidates": [], "promptFeedback": {"blockReason": "OTHER"}}),
        _respuesta_ok(_json_reunion_sin_campos_internos()),
    ]
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)

    resultado = proveedor.generar_estructurado("prompt", ResultadoReunion)

    modelos = [_modelo_de(p["url"]) for p in llamadas["posts"]]
    assert modelos == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert isinstance(resultado, ResultadoReunion)
    assert proveedor.ultimo_modelo == "gemini-3.6-flash"


def test_gemini_timeout_cae_al_respaldo_sin_repetir_el_mismo_modelo(llamadas):
    # Un ReadTimeout puede haberse procesado (y cobrado) en el servidor: no se repite el mismo modelo
    llamadas["respuestas"] = [
        requests.ReadTimeout("Read timed out. (read timeout=60.0)"),
        _respuesta_ok(_json_reunion_sin_campos_internos()),
    ]
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)

    resultado = proveedor.generar_estructurado("prompt", ResultadoReunion)

    modelos = [_modelo_de(p["url"]) for p in llamadas["posts"]]
    assert modelos == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert llamadas["esperas"] == []
    assert isinstance(resultado, ResultadoReunion)


def test_gemini_error_final_nombra_el_error_de_ambos_modelos(llamadas):
    llamadas["respuestas"] = [
        _RespuestaFalsa(503, texto="UNAVAILABLE"),
        _RespuestaFalsa(503, texto="UNAVAILABLE"),
        _RespuestaFalsa(404, texto="NOT_FOUND"),
    ]
    proveedor = ProveedorGemini(api_key=CLAVE_FALSA)

    with pytest.raises(ErrorProveedorLLM) as info:
        proveedor.generar_estructurado("prompt", ResultadoReunion)

    mensaje = str(info.value)
    assert "gemini-3.8-flash" in mensaje and "503" in mensaje
    assert "gemini-3.6-flash" in mensaje and "404" in mensaje
    # El mensaje se puede imprimir en una consola Windows (cp1252) sin UnicodeEncodeError
    mensaje.encode("cp1252")


# ---------------------------------------------------------------------------
# A8. Ollama: timeout configurable (600 s por defecto) y num_ctx 8192
# ---------------------------------------------------------------------------

def test_ollama_timeout_600_y_num_ctx_8192_por_defecto(llamadas, monkeypatch):
    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)
    llamadas["respuestas"] = [_RespuestaFalsa(200, {"response": _json_reunion_sin_campos_internos()})]
    proveedor = ProveedorOllama(host="http://localhost:11434")

    resultado = proveedor.generar_estructurado("prompt", ResultadoReunion)

    post = llamadas["posts"][0]
    assert post["timeout"] == 600.0
    assert post["json"]["options"]["num_ctx"] == 8192
    assert post["json"]["options"]["temperature"] == 0.0
    assert isinstance(resultado, ResultadoReunion)


def test_ollama_timeout_configurable_por_parametro_y_entorno(llamadas, monkeypatch):
    llamadas["respuestas"] = [
        _RespuestaFalsa(200, {"response": _json_reunion_sin_campos_internos()}),
        _RespuestaFalsa(200, {"response": _json_reunion_sin_campos_internos()}),
    ]
    monkeypatch.setenv("OLLAMA_TIMEOUT", "900")
    ProveedorOllama(host="http://localhost:11434").generar_estructurado("p", ResultadoReunion)
    ProveedorOllama(host="http://localhost:11434", timeout=30.0).generar_estructurado("p", ResultadoReunion)

    assert [p["timeout"] for p in llamadas["posts"]] == [900.0, 30.0]
