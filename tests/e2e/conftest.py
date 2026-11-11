"""Aislamiento del entorno para las pruebas AppTest de la app Streamlit.

La app llama a ``load_dotenv()`` al arrancar. En las pruebas se neutraliza para que
el ``.env`` real del desarrollador nunca cargue una clave en el proceso de pytest
y para que ninguna prueba llame a la API de Gemini. ``GEMINI_API_KEY`` queda vacía
por defecto; cada prueba que necesite una clave define una clave falsa.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def entorno_sin_claves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deja GEMINI_API_KEY vacía y evita que la app lea el .env real."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
