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
- **Evidencia validada con usuarios:** 2 conversaciones cualitativas reales con usuarios potenciales documentadas en `docs/research/` ([conversacion-01](docs/research/conversacion-01.md), [conversacion-02](docs/research/conversacion-02.md)): ambas personas graban 1–3 veces por semana con su propio celular, vuelven a escuchar grabaciones completas de 1 a 2 horas para repasar y no comprarían una grabadora dedicada como Plaud, prefiriendo usar software accesible en su smartphone.

---

## 4. Solución e Insight

- **Captura con el celular que ya tienes:** Graba con la grabadora nativa de tu teléfono inteligente en modo avión y sube el archivo (`.m4a`, `.mp3`, `.wav`) directamente desde el navegador móvil.
- **El formato adecuado para cada grabación:**
  - **Ponencia / Clase / Charla (Notas de clase):** Resumen general, ideas clave y preguntas con citas literales, más mapa mental interactivo con markmap.js.
  - **Reunión de Trabajo (Notas de reunión):** Resumen ejecutivo, temas tratados, acuerdos formales y tareas to-do con responsable y fecha límite (sin mapa mental innecesario).
  - **Entrevista / Conversación (Esquema por temas):** Esquema temático jerárquico en lista indentada con `[mm:ss]` y cita literal en cada punto (sin diagrama markmap), más libro de códigos.
  - **En todas:** Pestaña de transcripción completa con marcas de tiempo `[mm:ss]` y descarga directa en `.txt`.
- **Mapa mental interactivo con markmap.js:** Visualización jerárquica clara (2 a 4 niveles, 4 a 8 ramas) renderizada con tecnología ligera y responsiva (exclusiva para clases y ponencias).
- **Verificabilidad estricta segundo a segundo:** Cada nodo hijo del mapa mental y cada tarea incluyen su marca de tiempo exacta `[mm:ss]` y su cita textual literal verificada matemáticamente contra la transcripción (`validar_evidencia_literal`). Al hacer clic en `▶ [mm:ss]`, el reproductor salta al segundo exacto donde se pronunció la frase.
- **To-Do lists y acuerdos confiables:** Extracción automatizada de acuerdos y tareas pendientes con responsable y fecha límite, respaldados por evidencia literal.
- **Exportación en un clic:** Descarga directa en **Markdown (`.md`)**, **Mapa Mental HTML autónomo (`.html`)**, **Microsoft Word (`.docx`)** formateado y **Microsoft Excel (`.xlsx`)** con hojas de cálculo estructuradas.
- **Modo privado local:** Opción 100% desconectada que corre faster-whisper (int8) y Ollama (`qwen3:4b`) directamente en la laptop para máxima confidencialidad.

---

## 5. Why Now?

1. **Madurez de modelos de voz eficientes en CPU:** `faster-whisper 1.2.1` con int8 y VAD procesa una hora de audio en apenas **8.0 minutos en una laptop estándar** (RTF 0.1336, 404 MB RAM), permitiendo transcripción local sin GPU.
2. **LLMs ultraligeros con costo marginal reducido:** Modelos como **Gemini 2.5 Flash** junto a faster-whisper procesan 1 hora de audio por aproximadamente **S/ 0.064 soles** ($0.017 USD), permitiendo márgenes de contribución cercanos al 90%.
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
- **Transcripción acústica (Whisper small CPU):** ~8 minutos por hora de audio (US$ 0.0053 en cómputo nube, o S/ 0.00 en laptop del usuario).
- **Consumo de tokens LLM:** ~14,000 tokens de entrada y ~3,000 tokens de salida (incluyendo razonamiento y estructura) por hora de audio transcrito vía Map-Reduce.
- **Tarifas vigentes Gemini 2.5 Flash (10/11/2026, [ai.google.dev](https://ai.google.dev/gemini-api/docs/pricing)):** US$ 0.30 / 1M input y US$ 2.50 / 1M output = US$ 0.0117.
- **Costo total de cómputo por hora:** **US$ 0.017 (~S/ 0.064 soles por hora)** a tipo de cambio oficial 1 USD = 3.75 PEN (SBS / BCRP, 10/11/2026).

### Planes de suscripción en soles

| Plan | Precio | Horas de Audio / Mes | Costo Marginal Directo | Margen de Contribución Mensual | Margen de Contribución (%) |
|---|---|---|---|---|---|
| **Gratis** | **S/ 0** | Hasta 2 horas | S/ 0.13 / mes | -S/ 0.13 | N/A (adquisición) |
| **Estudiante** | **S/ 9.90 / mes** | Hasta 15 horas | S/ 0.96 / mes | **+S/ 8.94 / mes** | **90.3 %** |
| **Pro** | **S/ 24.90 / mes** | Hasta 40 horas | S/ 2.56 / mes | **+S/ 22.34 / mes** | **89.7 %** |

*Comparación frente a alternativas:*
- **Frente a PLAUD Note:** Plaud exige un pago inicial de US\$ 159–189 (~S/ 600–710 soles) más suscripciones adicionales para minutos extendidos. Minuta aprovecha el teléfono existente y ofrece planes en moneda local desde S/ 9.90/mes.
- **Frente a Google NotebookLM y Zoom AI Notes:** NotebookLM no enlaza el audio segundo a segundo con reproductor interactivo ni extrae to-dos con responsable; Zoom AI Notes se orienta a reuniones corporativas en inglés. Ninguno ofrece modo privado desconectado ni mapas mentales interactivos con trazabilidad de citas literales.

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
