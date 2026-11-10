# AGENTS.md: Enjambre de Agentes para Minuta

Este repositorio implementa el proyecto final de la Diplomatura Q-Lab PUCP ("Minuta") usando un enjambre de agentes coordinados en **Google Antigravity** con el modelo **Gemini 3.8 Flash**.

---

## 1. Metodología

- **ODD (Organic-Driven Development):** Desarrollo guiado por documento de feature (`odd/tasks/minuta.md`), test-first, y unidades revisables acotadas con Risk lines.
- **HDD (Hypothesis-Driven Development):** Validación experimental pre-registrada de las hipótesis H1 a H9 con oráculos reproducibles antes de comprometer el diseño de producción.

---

## 2. Roles del Enjambre

1. **Lead Senior Project Manager (`lead-pm` - Orquestador Inline):**
   - Mantiene la conversación principal en Antigravity.
   - Único autorizado para realizar commits, cambios en dependencias globales (`requirements.txt`), y orquestación de ramas en Git.
   - Responsable del documento ODD, memoria en Engram (`odd/minuta/tasks`), README y seam check final.
2. **Senior Data Scientist (`ds`):**
   - Superficie: `entrenamiento/generar_sinteticos.py`, `entrenamiento/etiquetar.py`, `entrenamiento/datos/**`, `evaluacion/**`, `docs/resultados.md`.
   - Generación de datos sintéticos con API de Gemini y salida estructurada Pydantic.
   - Oráculos reproducibles para H1, H4, H5a, H5b, H8, H9 y cálculo de costo por hora de audio.
3. **Senior ML Engineer - Audio (`ml-audio`):**
   - Superficie: `minuta/transcribir.py`, `minuta/glosario.py`, `tests/unit/test_transcribir.py`, `tests/unit/test_glosario.py`.
   - Transcripción con faster-whisper (int8, VAD), glosario de investigación en `initial_prompt` y CLI.
4. **Senior ML Engineer - NLP (`ml-nlp`):**
   - Superficie: `minuta/esquemas.py`, `minuta/estructurar.py`, `minuta/proveedores.py`, `minuta/detector.py`, `minuta/__init__.py`, `data/fixtures/**`, `entrenamiento/finetune_mmbert*`.
   - Contrato Pydantic v2 congelado en T01 (`NodoMapa`, `MapaMental`, plantillas con citas obligatorias).
   - Estructuración Map-Reduce por bloques de ~10 min y afinamiento de mmBERT-small.
5. **Senior UI/UX Designer (`ux`):**
   - Superficie: `app/**`, `.streamlit/**`, `minuta/exportar.py`, `minuta/mapa_html.py`, `data/demo/**`, `tests/unit/test_exportar.py`.
   - Interfaz responsiva en Streamlit optimizada para teléfonos celulares (una columna, botones táctiles).
   - Componente visual interactivo con markmap.js (versión CDN fija) y reproductor enlazado a minutos.
6. **Senior QA Engineer (`qa`):**
   - Superficie: `tests/e2e/**`, `scripts/verificar.py`, `docs/qa/**`.
   - Suite `scripts/verificar.py` (código 0 si pytest pasa, sin secretos, sin audio en índice y sin `.env` trackeado).
   - Verificador independiente de despliegue y seguridad de credenciales.

---

## 3. Reglas Operativas Obligatorias

1. **Privacidad y Datos (L21):**
   - **Ningún audio se versiona ni se publica.** Todo el audio va a `data/privado/` (ignorado en `.gitignore`).
   - Las grabaciones de prueba son ficticias, actuadas o sintéticas; nunca se usan reuniones reales de terceros sin consentimiento explícito.
   - La demo pública solo utiliza texto precalculado (`data/demo/`).
2. **Git y Commits:**
   - Rama activa: `feat/minuta`.
   - Solo el Lead PM realiza commits en el repositorio local.
   - Commits en español con Conventional Commits (`feat(...)`, `test(...)`, `docs(...)`) por unidad revisable.
3. **Superficies de Edición Estrictas:**
   - Cada subagente escribe únicamente dentro de su superficie autorizada (`Allowed edit surfaces`).
4. **Validación Determinista:**
   - Temperatura 0 en LLMs y semillas fijas en scripts y modelos.
   - Caché de modelos fuera del repositorio (`%LOCALAPPDATA%\minuta-cache`).
