# Checklist de la sección 9 de la consigna

- **Proyecto:** Minuta.
- **Curso:** Diplomatura de Especialización en Ciencia de Datos de Q-Lab PUCP. Docente: Alexander Quispe.
- **Entrega del link:** martes 10 de noviembre de 2026, hasta las 11:59 p. m., en el issue #204.
- **Presentación:** miércoles 11 de noviembre de 2026, 7:43 p. m. (turno 12).

---

## Estado por criterio

| # | Criterio de la consigna | Estado | Evidencia y lo que falta |
|---|---|:---:|---|
| **1** | Repo público con el README de la sección 4, LICENSE, .env.example y .gitignore. | 🟡 Parcial | `LICENSE` (MIT), `.env.example` y `.gitignore` versionados. El README tiene las 9 partes, con espacios pendientes (URL, capturas, video y foto). Hacer público el repo es decisión del founder. |
| **2** | Demo funcionando: en una URL pública o, como mínimo, en su laptop. | 🟡 Parcial | En local: `streamlit run app/streamlit_app.py` (ver la sección 6 del README). Las pruebas de `tests/e2e/` cubren el arranque, el modo demo y el error sin clave. URL pública: pendiente. |
| **3** | Video de respaldo de 60 a 90 segundos, con el link en el README. | ⚪ Pendiente | Contenido previsto: grabar con el celular → subir → notas → ▶ minuto → exportar. El enlace va en la sección 6 del README. |
| **4** | Diagrama de arquitectura y tres capturas en docs/. | 🟡 Parcial | Diagrama en [docs/arquitectura.md](../arquitectura.md) y en la sección 6 del README. Las 3 capturas en `docs/capturas/` están pendientes; una debe ser desde el celular. |
| **5** | Notas de las 3 conversaciones con usuarios en docs/research/. | 🟡 Parcial | 2 de las 3 conversaciones requeridas: [conversación 01](../research/conversacion-01.md) y [conversación 02](../research/conversacion-02.md). Guion en [docs/research/guion.md](../research/guion.md). Falta la tercera. |
| **6** | Una sección del README con las herramientas del curso y dónde están en el código. | 🟢 Cumplido | Sección 8 del README: Whisper (`minuta/transcribir.py`) y LLMs con salidas estructuradas (`minuta/esquemas.py`, `minuta/estructurar.py` y `minuta/proveedores.py`), cada una con su razón. |
| **7** | Commits en varios días, no todos el último. | 🟢 Cumplido | `git log --format=%ad --date=short` muestra commits el 09/11/2026 y el 10/11/2026. |
| **8** | Ningún secreto en el repo. Revísenlo con git log -p buscando api_key, secret o token. | 🟡 Automatizado | `python scripts/verificar.py` revisa el historial (`git log -p`), los archivos del árbol, que `.env` no esté en el índice y que no haya audio. Correrlo justo antes de entregar. |
| **9** | El link en el issue #204 antes del martes 10 a las 11:59 p. m. | ⚪ Pendiente | Plantilla del issue: nombre, startup y one-liner, link del demo ("corre en local" mientras no haya URL), link del repo, herramientas del curso y video de respaldo. Publicarlo es decisión del founder. |
| **10** | Un ensayo con cronómetro: 3 minutos. | ⚪ Pendiente | Guion en [docs/pitch.md](../pitch.md): 0:00–0:30 problema, 0:30–2:30 demo en vivo y 2:30–3:00 negocio. |

---

## Leyenda

- 🟢 **Cumplido:** comprobado con evidencia directa.
- 🟡 **Parcial o automatizado:** la base existe; falta una parte o correr la verificación antes de entregar.
- ⚪ **Pendiente:** todavía no se hizo.

---

## Verificación antes de entregar

```powershell
pip install -r requirements-dev.txt
python scripts/verificar.py
```

El script termina con código 0 solo si la suite de pruebas (`pytest -q`) pasa, `.env` y el audio están fuera del índice de Git y no hay secretos en el historial.
