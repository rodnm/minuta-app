# Minuta: reglas del proyecto para Google Antigravity

Minuta es una **alternativa económica a las grabadoras con IA como Plaud que usa tu celular**. Grabas una ponencia, clase, charla, reunión o entrevista de ~1 hora con el teléfono, la subes y obtienes:
- transcripción;
- resumen;
- un **mapa mental interactivo**;
- listas de tareas.

Cada nodo y cada elemento lleva su minuto y su cita literal. Transcribe español con términos en inglés y tiene un modo local (experimental). Es el proyecto final de la Diplomatura Q-Lab PUCP (issue d2cml-ai/Data-Science-Python#204).

Plantillas: **Ponencia / Clase / Charla** (por defecto), **Reunión** y **Entrevista**. El mapa mental se arma con un LLM con salida estructurada (árbol `MapaMental`) y se dibuja con markmap.js, con una versión de CDN fija.

## Leer primero (orquestador)

1. `odd/tasks/minuta.md`: Specs, Hipótesis, Tasks y Log. Es el documento de feature ODD y es **local**.
2. `docs/plan/plan-maestro.md`: el plan detallado por etapas. También es **local**.
3. `docs/plan/roles.md`: las tarjetas de los 5 perfiles, listas para `define_subagent`. También es **local**.

La conversación principal actúa como **Lead Senior Project Manager**. Los demás perfiles (Data Scientist, ML Engineer audio/NLP, UI/UX Designer y QA Engineer) se definen con `define_subagent` y se ejecutan con `invoke_subagent`, por referencia: `Spec: odd/tasks/minuta.md, T#, S#, H#`.

## Metodología

- **ODD:** `C:\Users\DOKU\.gemini\antigravity-cli\skills\odd\SKILL.md`. Documento de feature, test-first, commits por unidad de trabajo y una Risk line en cada entrega.
- **HDD:** `C:\Users\DOKU\.gemini\antigravity-cli\skills\hdd\SKILL.md`. Las hipótesis H1–H9 están pre-registradas en `odd/tasks/minuta.md`, y sus umbrales no se cambian después de ver los datos.
- **Oleadas:** como máximo 3 trabajadores en paralelo, con superficies de edición disjuntas. Nunca dos trabajos pesados de modelo a la vez (Whisper, entrenamiento o evaluación).

## T00: antes del primer `git add` (obligatorio)

Agregar a `.git/info/exclude`, no a `.gitignore`, estas rutas locales:

```text
odd/
docs/plan/
docs/chatgpt-*.md
docs/Proyecto_Final_Startup_Diplomatura_QLAB.pdf
```

Después, comprobar con `git status --ignored` que no aparecen como archivos por versionar.

El `.gitignore` versionado debe incluir como mínimo:
- `.env`, `.venv/`, `__pycache__/` y `.streamlit/secrets.toml`;
- `data/privado/`, `modelos/`, `*.ckpt` y `*.safetensors`;
- **todo el audio:** `*.m4a`, `*.mp3`, `*.wav`, `*.ogg`, `*.webm` y `*.aac`.

## Git y autoría

- **El Lead PM es el único que hace commits.** Los trabajadores no hacen commit, no formatean todo el repo y no instalan nada global; si necesitan una dependencia, la piden en su reporte.
- **Rama:** `feat/minuta`. Commits en español con Conventional Commits (`feat(transcripcion): …`), en unidades revisables de ~400 líneas que incluyen sus pruebas y su documentación.
- **Coautoría con IA (decisión del usuario):** cada commit termina con la línea de la IA que realmente escribió la unidad:
  - enjambre en Antigravity: `Co-Authored-By: Gemini 3.8 Flash (Google Antigravity)`
  - Claude Code: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

  Los PR también declaran la coautoría.
- **Decisiones del usuario:** hacer push, abrir PR, hacer público el repo, publicar en el issue #204 y configurar los secrets de Streamlit Cloud. El agente prepara todo, pero no ejecuta estas acciones sin confirmación.

## Idioma

Español neutro y profesional, sin voseo ni regionalismos, en la UI, el README, la documentación, los comentarios y los mensajes de commit. Los identificadores siguen la estructura del plan (`minuta/transcribir.py`, `minuta/estructurar.py`, …).

## Datos y secretos

- No se usan datos personales de terceros sin consentimiento. El audio privado va en `data/privado/`, que no se versiona.
- **Ningún audio se versiona ni se publica.** Las grabaciones (reunión de demo, frases de evaluación, conversaciones con usuarios) quedan en `data/privado/`. Nunca se usa una reunión real de trabajo: la reunión de demo es actuada, con un guion ficticio, o generada con voces sintéticas.
- **Rutas de datos versionadas:** los sintéticos en `entrenamiento/datos/`, los fixtures del contrato en `data/fixtures/` y la demo precalculada **solo en texto** en `data/demo/`.
- **URL pública:** solo muestra ese texto ficticio y procesa el audio que el usuario sube en su sesión, sin guardarlo. Allí, ▶ minuto reproduce solo un audio que el usuario haya subido en su sesión; si no hay, muestra el minuto como texto.
- **Qué se publica de la evaluación y la investigación:** las métricas en `docs/resultados.md` y las notas anonimizadas de las conversaciones en `docs/research/`.
- **La API de Gemini solo recibe contenido ficticio.** El contenido real o sensible se procesa en modo local (Ollama).
- Las claves solo van en `.env` (local) o en los secrets de Streamlit Cloud. `.env.example` lleva solo los nombres: `GEMINI_API_KEY`, `MINUTA_PROVEEDOR`, `OLLAMA_HOST`.
- Caché de modelos fuera del repo:
  - `HF_HOME=%LOCALAPPDATA%\minuta-cache\hf`
  - `WHISPER_CACHE=%LOCALAPPDATA%\minuta-cache\whisper`

## Comandos

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
pip install -r requirements-dev.txt         # pruebas y evaluación (pytest, psutil, numpy)
pytest -q                                   # suite completa
python scripts/verificar.py                 # pruebas + secretos + .env fuera del índice
streamlit run app/streamlit_app.py          # app (.env con GEMINI_API_KEY; el modo demo arranca apagado)
python -m minuta.transcribir <audio> --modelo small --salida out.json
python -m evaluacion.<terminos|velocidad|detector|todos|eficiencia|validez_json> ...
```

## Puertas de calidad

- **Puerta 1:** H1, H2, H3 y H6 decididas en el Log. Con eso se fijan el modelo de Whisper por modo y el LLM local.
- **Puerta 2:** cada unidad revisada contra su superficie, con un comando vuelto a correr por el PM y su commit propio.
- **Puerta 3:** URL pública verificada por QA como verificador independiente (despliegue: riesgo 5; claves: riesgo 2).
- **Cierre:** `pytest -q` y `python scripts/verificar.py` en verde, README con las 9 partes, `docs/research/` con 3 conversaciones, video de 60–90 s y checklist de la sección 9 de la consigna completo.
