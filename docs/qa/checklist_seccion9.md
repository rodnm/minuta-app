# Checklist de Evaluación — Sección 9 de la Consigna PUCP

**Proyecto:** Minuta (Alternativa económica a Plaud con tu celular y mapas mentales)  
**Curso:** Ciencia de Datos con Python Intermedio — Diplomatura Q-Lab PUCP  
**Docente:** Alexander Quispe  
**Responsable de seguimiento:** Senior QA Engineer (`qa`)  
**Fecha límite de entrega:** Martes 10 de noviembre de 2026, 11:59 p. m. (Issue #204)  
**Fecha de presentación:** Miércoles 11 de noviembre de 2026, 7:43 p. m. (Turno 12)

---

## Matriz de Cumplimiento de Criterios (Sección 9 del PDF)

| # | Criterio de la Consigna | Estado Actual | Evidencia Observada y Ubicación | Responsable / Tarea |
|---|---|:---:|---|---|
| **1** | **Repo público con el README de la sección 4, LICENSE, .env.example y .gitignore.** | 🟡 Parcial (En curso) | • `LICENSE` (MIT) versionado.<br>• `.env.example` con variables sin secretos.<br>• `.gitignore` configurado con exclusión de audios y `.env`.<br>• README contiene el esqueleto de las 9 partes de la sección 4.<br>• El pase a público se realizará en HU09 por decisión del usuario. | PM (`lead-pm`)<br>T00 / T30 / HU09 |
| **2** | **Demo funcionando: en una URL pública o, como mínimo, en su laptop.** | 🟢 Cumplido en local / 🟡 Pendiente URL pública | • En local: `streamlit run app/streamlit_app.py` corre perfectamente en modo demo con fixtures locales sin red.<br>• Prueba de humo automatizada `tests/e2e/test_smoke.py` pasando en verde con Streamlit AppTest.<br>• Despliegue en Streamlit Cloud programado en HU03 / HU07 / T24. | UX (`ux`) / QA (`qa`)<br>T06 / T07 / T24 |
| **3** | **Video de respaldo de 60 a 90 segundos, con el link en el README.** | ⚪ Pendiente | • Duración requerida: 60 a 90 segundos.<br>• Contenido: Grabar con celular → subir → mapa mental → ▶ minuto → exportar.<br>• Enlace se colocará en la sección Demo del `README.md`. | Humano (`HU`)<br>HU08 |
| **4** | **Diagrama de arquitectura y tres capturas en docs/.** | ⚪ Pendiente | • Requiere: Diagrama de arquitectura del flujo y 3 capturas en `docs/capturas/` (incluyendo obligatoriamente una captura tomada desde la vista de celular móvil).<br>• Programado para la unidad T23 tras la integración de T21. | UX (`ux`)<br>T23 |
| **5** | **Notas de las 3 conversaciones con usuarios en docs/research/.** | 🟡 En curso | • Guion semiestructurado elaborado en `docs/research/guion.md`.<br>• Contactos mapeados (compañeros de diplomatura, asistentes de investigación, economistas).<br>• Se publicarán únicamente las notas crudas y anonimizadas. | Humano (`HU`)<br>HU01 / HU04 |
| **6** | **Una sección del README con las herramientas del curso y dónde están en el código.** | 🟡 En consolidación | • Mapeo inicial definido en el README:<br>  - Whisper (sesión 13) → `minuta/transcribir.py`<br>  - LLMs estructurados (sesión 08) → `minuta/estructurar.py`<br>  - Fine-tuning mmBERT (sesión 09) → `minuta/detector.py`<br>  - Evaluación (sesión 12) → `evaluacion/`<br>  - Dashboard Streamlit (sesión 05) → `app/streamlit_app.py`. | PM (`lead-pm`)<br>T30 |
| **7** | **Commits en varios días, no todos el último.** | 🟢 Cumplido | • Commits iniciados el lunes 09/11 (T00, T01, T02, T06, T03) y continuando el martes 10/11 y miércoles 11/11.<br>• Unidades de trabajo atómicas (~400 líneas), mensajes con Conventional Commits y coautoría explícita declarada. | PM (`lead-pm`)<br>T00–T41 |
| **8** | **Ningún secreto en el repo. Revísenlo con git log -p buscando api_key, secret o token.** | 🟢 Cumplido y Automatizado | • Verificado automáticamente mediante `scripts/verificar.py`.<br>• Escaneo de `git log -p` y archivos del árbol sin hallazgos de claves (`AIza`, `sk-`, `ghp_`, tokens, llaves privadas).<br>• `.env` estrictamente fuera del índice de Git (`git ls-files .env` vacío). | QA (`qa`)<br>T07 / `scripts/verificar.py` |
| **9** | **El link en el issue #204 antes del martes 10 a las 11:59 p. m.** | ⚪ Pendiente | • Plantilla oficial preparada con los campos: Nombre, Startup y one-liner, Link del demo, Link del repo, Herramientas del curso, Video de respaldo.<br>• Publicación manual en el issue https://github.com/d2cml-ai/Data-Science-Python/issues/204. | Humano (`HU`)<br>HU09 |
| **10** | **Un ensayo con cronómetro: 3 minutos.** | ⚪ Pendiente | • Turno asignado: Miércoles 11/11 a las 7:43 p. m. (Turno 12).<br>• Estructura estricta: 0:00–0:30 problema y usuario, 0:30–2:30 demo en vivo con celular, 2:30–3:00 modelo de negocio y cierre.<br>• Se requieren 3 ensayos con cronómetro previo a la sesión. | PM (`lead-pm`) / Humano (`HU`)<br>T41 / HU11 |

---

## Leyenda de Estados
- 🟢 **Cumplido:** Verificado con evidencia empírica directa o prueba técnica automatizada.
- 🟡 **En curso / Parcial:** Estructura o componente base construido; pendiente de datos de usuario o integración final.
- ⚪ **Pendiente:** Tarea programada en el cronograma de etapas posteriores (Etapas 3, 4 o 5).

---

## Verificación de Integridad Automatizada Asociada

Para garantizar el cumplimiento de los ítems de seguridad y código sin degradación durante las siguientes oleadas, se debe ejecutar periódicamente:

```powershell
python scripts/verificar.py
```

El script retornará `0` únicamente cuando los ítems técnicos (pruebas pytest, exclusión de `.env`, exclusión de audio L21 y ausencia de secretos en git log) estén rigurosamente validados.
