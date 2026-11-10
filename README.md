# Minuta

> Alternativa económica a las grabadoras con IA (como Plaud) que usa tu propio teléfono celular para generar resúmenes, tareas y mapas mentales interactivos y verificables.

---

## 1. One-liner

Convertimos lo que grabas con tu celular (ponencias, clases o reuniones) en resumen, tareas y mapas mentales verificables, en español con términos en inglés, sin pagar una grabadora de hardware como Plaud.

## 2. Founder

Desarrollado por **Rodrigo Norabuena**, practicante profesional de gestión de la investigación con experiencia en flujos ETL, bases de datos, dashboards y analítica de datos en CENTRUM PUCP. El proyecto nace de la vivencia directa de la carga operativa que representa documentar, transcribir y estructurar reuniones de trabajo, charlas académicas y entrevistas.

## 3. Problema

- **Tiempo:** transcribir a mano una hora de audio puede tomar unas 4 horas, según estimaciones de servicios de transcripción. Las conversaciones con usuarios dirán cuánto les toma a ellos.
- **Hardware:** la grabadora Plaud Note cuesta US\$ 159 y la Note Pro US\$ 189. Incluyen 300 minutos de transcripción al mes; para usar más hay que pagar un plan.
- **Términos en inglés dentro del español:** en investigación se dice *journal*, *paper*, *peer review* o *Scopus* en medio de frases en español, y un transcriptor automático puede escribirlos mal. Minuta lo mide: comparamos cuántos de esos términos salen bien con y sin glosario (hipótesis H1).
- **Privacidad:** algunas grabaciones, como entrevistas con consentimiento informado o reuniones internas, no deberían subirse a servicios externos. Las conversaciones con usuarios dirán cuánto pesa esto para ellos.
- **Evidencia de usuarios:** 3 conversaciones con usuarios potenciales, documentadas en `docs/research/` (en curso).

## 4. Solución e Insight

- **Captura sin fricción:** Graba directamente con tu teléfono inteligente y sube el audio (o graba clips rápidos en el navegador).
- **Mapa mental interactivo con markmap.js:** Visualización jerárquica clara de ideas centrales y secundarias.
- **Verificabilidad estricta:** Cada nodo del mapa y cada tarea incluyen su minuto de inicio `[mm:ss]` y su cita textual literal para auditoría y reproducción instantánea.
- **Glosario guiado ES-EN:** Corrección contextual de términos especializados de investigación mediante `initial_prompt`.
- **Privacidad por diseño:** Modo nube que no almacena audio en servidores y modo local (Ollama + Whisper en CPU) para confidencialidad total.

## 5. Why Now?

1. **Madurez de modelos eficientes en CPU:** Modelos de ASR optimizados (faster-whisper) y LLMs compactos (Qwen, Gemini Flash) procesan audio y generan salidas estructuradas en hardware cotidiano.
2. **Visualización ligera:** Componentes interactivos como markmap permiten explorar árboles conceptuales en cualquier pantalla sin dependencias pesadas.
3. **Exigencia regulatoria y ética:** Marco ético y de protección de datos (como las directivas de Indecopi y privacidad en investigación) que exige trazabilidad y procesamiento seguro.

## 6. Demo

- **URL pública:** Despliegue en Streamlit Community Cloud (modo demo precalculado y procesamiento en sesión).
- **Uso en vivo:**
  1. Selecciona la plantilla: **Ponencia / Clase / Charla** (por defecto), **Reunión** o **Entrevista**.
  2. Sube un archivo de audio (`.m4a`, `.mp3`, `.wav`) grabado con tu celular.
  3. Visualiza la transcripción, el resumen ejecutivo, la lista de to-do y el mapa mental interactivo.
  4. Haz clic en ▶ minuto para escuchar el fragmento exacto en el reproductor de audio integrado.
  5. Exporta el mapa mental en Markdown/HTML y el informe en Word/Excel.
- **Video de respaldo (60–90 s):** Enlace disponible tras el cierre de la etapa de evaluación.

## 7. Modelo de Negocio

Estructura de precios simple orientada al mercado hispanohablante y universitario:

| Plan | Precio | Alcance mensual | Modo / Privacidad |
|---|---|---|---|
| **Gratis** | S/ 0 | Hasta 2 horas de audio | Nube (sesión temporal) |
| **Estudiante** | S/ 9.90 / mes | Hasta 15 horas de audio | Nube + exportaciones |
| **Pro / Investigador** | S/ 24.90 / mes | Hasta 40 horas de audio | Nube + Modo Local ilimitado + soporte prioritario |

*Comparación:* Plaud exige hardware de US\$ 159–189 más suscripción anual (US\$ 239); NotebookLM ofrece mapas mentales pero con servidores en la nube sin soporte de audio local ni glosario bilingüe auditable por minuto.

## 8. Herramientas del Curso

- **Sesión 13 (Whisper):** Transcripción rápida y precisa con faster-whisper en `minuta/transcribir.py`.
- **Sesión 08 (LLM con salidas estructuradas):** Extracción con esquemas Pydantic para resúmenes, tareas y el árbol `MapaMental` en `minuta/estructurar.py`.
- **Sesión 09 (Fine-tuning de ModernBERT):** Detector `mmBERT-small` para clasificar fragmentos (`idea`, `tarea`, `acuerdo`, `pregunta`, `relleno`) y reducir el consumo de tokens en `minuta/detector.py`.
- **Sesión 12 (Evaluación):** Arnés de evaluación cuantitativa de hipótesis H1 a H9 en `evaluacion/`.
- **Sesión 05 (Dashboard interactivo):** Interfaz web responsiva con Streamlit pensada para celular en `app/streamlit_app.py`.

## 9. Qué Hizo el Agente

- **Claude Code:** Levantamiento inicial de requerimientos, filtrado de ideas y diseño del plan maestro v2.
- **Enjambre Google Antigravity (Gemini 3.8 Flash):** Implementación bajo metodología ODD y validación HDD:
  - *Lead Senior Project Manager (PM):* Orquestación, control de git, documentación y seam checks.
  - *Senior Data Scientist (DS):* Generación de sintéticos, arneses de evaluación y cálculo de costos.
  - *Senior ML Engineer Audio (ML-a):* Transcripción con faster-whisper y glosario.
  - *Senior ML Engineer NLP (ML-n):* Contratos Pydantic, mapa mental, estructuración y afinamiento de mmBERT.
  - *Senior UI/UX Designer (UX):* Interfaz Streamlit para celular, componente markmap y exportaciones.
  - *Senior QA Engineer (QA):* Arnés `scripts/verificar.py`, pruebas e2e y verificación independiente.
