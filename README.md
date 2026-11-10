# Minuta

> Alternativa económica a las grabadoras con IA (como Plaud) que usa tu propio teléfono celular para generar resúmenes, tareas y mapas mentales interactivos y verificables.

---

## 1. One-liner

Convertimos lo que grabas con tu celular (ponencias, clases, reuniones o entrevistas) en resúmenes ejecutivos, listas de tareas y **mapas mentales interactivos verificables por minuto y cita literal**, en español con términos técnicos en inglés, sin pagar una grabadora de hardware como Plaud.

---

## 2. Founder & Contexto

Desarrollado por **Rodrigo Norabuena**, asistente de investigación con experiencia en analítica de datos, flujos ETL, bases de datos y dashboards en una escuela de negocios líder en Lima, y estudiante del Diplomado en Ciencia de Datos de Q-Lab PUCP. 

El proyecto nace de la vivencia directa de la pesada carga operativa que representa documentar, transcribir y estructurar reuniones de proyectos de investigación, ponencias académicas y entrevistas en profundidad.

---

## 3. Problema

- **Tiempo excesivo:** Transcribir y resumir a mano una sola hora de audio toma aproximadamente 4 horas de trabajo, según estimaciones de servicios de transcripción.
- **Barrera económica de hardware:** Las grabadoras dedicadas con IA como PLAUD Note cuestan entre **US\$ 159 y US\$ 189**. Aunque incluyen 300 minutos al mes en su plan base, adquirir minutos ilimitados exige suscribirse a un plan anual de **US\$ 239.99**. No existen precios oficiales en moneda local (soles) y obligan al usuario a cargar y sincronizar un dispositivo físico adicional.
- **Términos en inglés dentro del español:** En investigación y consultoría se emplean constantemente términos mixtos (*paper*, *journal*, *peer review*, *grant*, *ablation study*). En nuestras mediciones empíricas con grabaciones reales (H1), la línea base acústica de Whisper confundió términos técnicos altamente específicos como *arXiv* (transcrito como `"RCIP"`) o *editorial board* (transcrito como `"digital board"`). Minuta aborda esta brecha mediante normalización y corrección contextual en la etapa de estructuración con el LLM.
- **Privacidad y confidencialidad:** En proyectos de investigación y reuniones de trabajo se maneja información sujeta a convenios de confidencialidad o privacidad, por lo que los usuarios valoran una opción de procesamiento local o privado.

---

## 4. Solución e Insight

- **Captura con el celular que ya tienes:** Graba con la grabadora nativa de tu teléfono inteligente en modo avión y sube el archivo (`.m4a`, `.mp3`, `.wav`) directamente desde el navegador móvil.
- **Mapa mental interactivo con markmap.js:** Visualización jerárquica clara (2 a 4 niveles, 4 a 8 ramas) renderizada con tecnología ligera y responsiva.
- **Verificabilidad estricta segundo a segundo:** Cada nodo hijo del mapa mental y cada tarea incluyen su marca de tiempo exacta `[mm:ss]` y su cita textual literal verificada matemáticamente contra la transcripción (`validar_evidencia_literal`). Al hacer clic en `▶ [mm:ss]`, el reproductor salta al segundo exacto donde se pronunció la frase.
- **To-Do lists y acuerdos confiables:** Extracción automatizada de acuerdos y tareas pendientes con responsable y fecha límite, respaldados por evidencia literal.
- **Exportación en un clic:** Descarga directa en **Markdown (`.md`)**, **Mapa Mental HTML autónomo (`.html`)**, **Microsoft Word (`.docx`)** formateado y **Microsoft Excel (`.xlsx`)** con hojas de cálculo estructuradas.
- **Modo privado local:** Opción 100% desconectada que corre faster-whisper (int8) y Ollama (`qwen3:4b`) directamente en la laptop para máxima confidencialidad.

---

## 5. Why Now?

1. **Madurez de modelos de voz eficientes en CPU:** `faster-whisper 1.2.1` con int8 y VAD procesa una hora de audio en apenas **8.0 minutos en una laptop estándar** (RTF 0.1336, 404 MB RAM), permitiendo transcripción local sin GPU.
2. **LLMs ultraligeros con costo marginal casi nulo:** Modelos como **Gemini 3.8 / 2.5 Flash** procesan 1 hora de transcripción por menos de **S/ 0.007 soles** ($0.0018 USD), abriendo márgenes de contribución superiores al 99%.
3. **Smartphones con micrófonos estéreo avanzados:** La calidad de captura de voz de los teléfonos móviles actuales hace innecesaria la compra de micrófonos dedicados de 180 dólares.

---

## 6. Demo

- **URL pública:** Despliegue en Streamlit Community Cloud con modo demo precalculado (solo texto sin red) y procesamiento en sesión.
- **Uso en vivo:**
  1. Selecciona la plantilla: **Ponencia / Clase / Charla** (por defecto), **Reunión** o **Entrevista**.
  2. Sube un archivo de audio grabado con el celular o activa el **Modo Demo**.
  3. Explora el **Mapa Mental interactivo** y pulsa en `▶ [mm:ss]` para saltar al fragmento de audio exacto.
  4. Revisa las ideas clave, acuerdos y tareas pendientes con sus respectivas citas textuales.
  5. Descarga la minuta en Markdown, HTML autónomo, Word o Excel en la sección de exportación.
- **Video de respaldo (60–90 s):** Enlace demostrativo paso a paso disponible para presentación.

---

## 7. Modelo de Negocio

### Costo unitario medido por hora de audio (S16)
- **Transcripción acústica:** S/ 0.00 (CPU local o servidor volátil).
- **Consumo de tokens LLM:** ~12,000 tokens de entrada y ~3,000 tokens de salida por hora de audio transcrito vía Map-Reduce.
- **Costo de API (Gemini Flash):** **$0.0018 USD (~S/ 0.007 soles por hora de audio)** en modo estándar, y **$0.0012 USD (~S/ 0.0045 soles)** con filtrado de relleno mmBERT.
- **Infraestructura:** S/ 0.00 (Streamlit Cloud Community).

### Planes de suscripción en soles

| Plan | Precio | Horas de Audio / Mes | Costo Marginal en APIs | Margen de Contribución Bruto |
|---|---|---|---|---|
| **Estudiante (Gratuito)** | **S/ 0** | Hasta 3 horas | S/ 0.02 / mes | N/A (adquisición de usuarios) |
| **Investigador** | **S/ 29 / mes** | Hasta 15 horas | S/ 0.11 / mes | **> 99.6 %** |
| **Laboratorio / Equipo** | **S/ 89 / mes** | Hasta 60 horas | S/ 0.42 / mes | **> 99.5 %** |

*Comparación frente a alternativas:*
- **Frente a PLAUD Note:** Plaud exige un pago inicial de US\$ 159–189 (~S/ 650–750 soles) más US\$ 240/año para uso ilimitado. Minuta usa tu propio celular y ofrece suscripciones en soles desde S/ 29/mes.
- **Frente a Google NotebookLM:** NotebookLM genera notas y mapas estáticos en la nube, pero no permite verificar la cita textual exacta segundo a segundo con reproductor enlazado, no extrae to-dos con responsable ni ofrece modo privado local desconectado.

---

## 8. Herramientas del Curso Utilizadas

- **Sesión 13 (Reconocimiento Automático de Voz):** Transcripción con faster-whisper (`small` int8, VAD) en `minuta/transcribir.py`.
- **Sesión 08 (LLMs con Salida Estructurada):** Extracción con esquemas Pydantic v2 congelados y verificación de evidencia literal en `minuta/estructurar.py`.
- **Sesión 09 (Fine-tuning de Transformers / mmBERT):** Clasificador multiclase `mmBERT-small` (5 categorías: `idea`, `tarea`, `acuerdo`, `pregunta`, `relleno`) para filtrado de relleno y ahorro de tokens en `entrenamiento/` y `minuta/detector.py`.
- **Sesión 12 (Evaluación y Validación Empírica):** Marco de trabajo HDD con 9 hipótesis pre-registradas y oráculos ejecutables en consola en `evaluacion/` y `docs/resultados.md`.
- **Sesión 05 (Dashboard Web Responsivo):** Interfaz Streamlit mobile-first con visualización markmap.js y exportaciones multi-formato en `app/streamlit_app.py`.

---

## 9. Qué Hizo el Agente

El desarrollo de Minuta se llevó a cabo mediante colaboración humano-agente bajo las metodologías **ODD (Organic-Driven Development)** y **HDD (Hypothesis-Driven Development)**:

- **Claude Code:** Levantamiento preliminar de requerimientos, diseño del plan maestro v2 y auditoría de decisiones clave (L25).
- **Enjambre de Agentes en Google Antigravity (Gemini 3.8 Flash):**
  - **Lead Senior Project Manager (inline):** Control estricto de Git, revisión de superficies autorizadas (Allowed edit surfaces), mantenimiento de la bitácora ODD (`odd/tasks/minuta.md`), sincronización de memoria en Engram (#1035) y seam checks globales.
  - **Senior Data Scientist:** Generación de 1,351 segmentos sintéticos con Gemini API (`sinteticos_entrenamiento.json`), arneses de evaluación cuantitativa y reporte integral de resultados (`docs/resultados.md`).
  - **Senior ML Engineer - Audio:** Módulo de transcripción (`minuta/transcribir.py`), inyección de hotwords por ventana y parches defensivos de compatibilidad (`minuta/compat.py`).
  - **Senior ML Engineer - NLP:** Contrato Pydantic v2 congelado, estructuración Map-Reduce por bloques de 10 min, notebook Colab de fine-tuning mmBERT y detector de segmentos (`minuta/detector.py`).
  - **Senior UI/UX Designer:** Dashboard en Streamlit optimizado para celular, componente HTML markmap y módulo de exportaciones multi-formato (`minuta/exportar.py`).
  - **Senior QA Engineer:** Suite `scripts/verificar.py` y pruebas E2E con Streamlit AppTest.

**Garantía de Seguridad y Privacidad:**
- 179 pruebas unitarias y E2E pasando en verde.
- 0 secretos ni credenciales en el historial de Git.
- 0 archivos de audio versionados en el repositorio (estricto cumplimiento de regla de privacidad L21).
- Archivo `.env` y carpetas de audio excluidos del índice.
