# Minuta

> Proyecto final de la Diplomatura de Especialización en Ciencia de Datos de Q-Lab PUCP. App pública: https://minuta-app.streamlit.app/

---

## 1. One-liner

**Graba. Sube. Vuelve al minuto exacto.** Minuta convierte la clase que grabaste con tu celular en notas donde cada idea te lleva a su momento en el audio, sin reescuchar dos horas.

---

## 2. Founder

**Rodrigo Norabuena.** Asistente de investigación con experiencia en analítica de datos, flujos ETL, bases de datos y dashboards en una escuela de negocios de Lima, y estudiante de la Diplomatura de Especialización en Ciencia de Datos de Q-Lab PUCP.

- **Foto:** pendiente (`docs/capturas/founder.jpg`).
- **Por qué este problema:** en mi trabajo documento reuniones de proyectos de investigación, ponencias académicas y entrevistas, donde el español se mezcla con términos en inglés.
- **Cómo cubro cada frente con agentes de IA:**
  - producto: Claude Code (investigación, plan y auditorías);
  - ingeniería y QA: un enjambre de Gemini 3.8 Flash en Google Antigravity;
  - diseño: el rol de diseño UI/UX del mismo enjambre;
  - ventas: todavía no hay un flujo de ventas; las conversaciones con usuarios fueron el primer contacto.

---

## 3. Problema

**Quién lo sufre:** universitarios que graban sus clases con el celular para repasarlas. También quienes graban charlas, reuniones de trabajo o entrevistas.

**Cuánto les cuesta:**
- Las 2 personas con las que conversé vuelven a escuchar grabaciones completas de 1 a 2 horas: "Si dura 1-2 horas lo voy a escuchar nuevamente" (conversación 01) y "usualmente hago grabaciones de 2 horas de mis clases y las escucho completas" (conversación 02).
- Una persona calcula más de 5 horas para transcribir una reunión (conversación 01): "Podría tardar más de 5 horas solo para una reunión".
- Cuando hay prisa, se busca a mano el momento: "si estoy apurada voy momento exacto donde quiero escuchar nuevamente la explicación" (conversación 02).

**Cómo lo resuelven hoy:**
- Reescuchan la grabación completa.
- Usan NotebookLM, que según la conversación 02 "no siempre recoge con precisión algunos términos técnicos o palabras en inglés".
- Usan Zoom AI Notes y luego ChatGPT o Gemini para resumir (conversación 01). La referencia de esa persona es la prueba gratuita de 3 usos de Zoom, que coincide con la cuota del plan Básico (ver la competencia en la sección 7).
- Existen grabadoras con IA como Plaud, pero ninguna de las 2 personas compraría una: "No pagaría porque es una inversión fuerte para algo que puedo hacer con mi celular" (conversación 02).

**Términos en inglés dentro del español:** en nuestra medición (H1), Whisper `small` acertó 43 de 50 términos (86 %) en 25 frases grabadas con el celular. Confundió *arXiv* con "RCIP" y *editorial board* con "digital board". El glosario en Whisper no mejoró el resultado (+0 pts). Minuta no altera la transcripción cruda: las citas son literales, pero en la estructuración posterior (H1b) identifica los términos en inglés esperados (98 % de recall) y muestra la forma canónica junto a lo transcrito cuando difieren (por ejemplo, JSON cuando se transcribió «Jason»).

**La nube:** una persona no subiría grabaciones con información personal o privada (conversación 02). La otra no sube grabaciones a la nube porque son archivos pesados (conversación 01).

**Evidencia de usuarios (n = 2):** 2 de las 3 conversaciones requeridas, en `docs/research/`: [conversación 01](docs/research/conversacion-01.md) y [conversación 02](docs/research/conversacion-02.md).
- Ambas personas graban con su celular entre 1 y 3 veces por semana, reescuchan grabaciones completas de 1 a 2 horas y no comprarían un Plaud.
- Límites: n = 2, respuestas por escrito y contactos del founder.
- La tercera conversación está pendiente.

---

## 4. Solución e insight

**Insight:** No buscan otro resumen: quieren volver al minuto exacto de una explicación sin reescuchar 2 horas (conversación 02).

### Hoy vs. con Minuta

| Paso del flujo | Hoy (lo que contaron las 2 personas) | Con Minuta |
|---|---|---|
| **1. Grabar** | Graban con el celular: *"grababa todas mis clases de la universidad en el celular"* (conversación 01) y *"Sí, suelo grabar clases de la universidad y algunas charlas con mi celular"* (conversación 02). Rechazan comprar un aparato dedicado: *"No pagaría porque es una inversión fuerte para algo que puedo hacer con mi celular y que me funciona bien aun si no es perfecto siempre."* (conversación 02). | Sigues usando tu celular como grabadora, sin comprar hardware adicional. |
| **2. Repasar** | Reescuchan audios completos de 1 a 2 horas para no transcribir a mano: *"Si dura 1-2 horas lo voy a escuchar nuevamente."* y *"Podría tardar más de 5 horas solo para una reunión"* (conversación 01); *"usualmente hago grabaciones de 2 horas de mis clases y las escucho completas"* (conversación 02). | Subes el audio y obtienes notas estructuradas (resumen, ideas clave, tareas y preguntas) en minutos. |
| **3. Buscar una explicación** | Adelantan a ciegas buscando el momento exacto: *"si estoy apurada voy momento exacto donde quiero escuchar nuevamente la explicación para complementar mis apuntes."* (conversación 02). | Cada idea, nodo del mapa y tarea incluye el botón ▶ `[mm:ss]` para saltar al inicio del segmento que contiene la cita. |
| **4. Términos técnicos y mapa mental** | Las herramientas que usan tienen límites con términos o no conectan con el audio: *"no siempre recoge con precisión algunos términos técnicos o palabras en inglés"* (conversación 02 sobre NotebookLM). | Cada punto del resumen y del mapa mental se valida contra la transcripción: solo se conservan citas textuales comprobadas con la marca de tiempo de su segmento. |

**Qué construí:**
- **Captura con el celular:** grabas con la grabadora del teléfono y subes el archivo (`.m4a`, `.mp3` o `.wav`) desde el navegador.
- **Un formato por tipo de grabación:**
  - **Ponencia / Clase / Charla:** notas de clase (resumen, ideas clave y preguntas) y un mapa mental con markmap.js.
  - **Reunión:** notas de reunión (resumen, temas, acuerdos y tareas con responsable y fecha límite).
  - **Entrevista:** esquema por temas, con minuto y cita en cada punto, y un libro de códigos.
  - **En todas:** la transcripción completa con marcas `[mm:ss]`.
- **Cada punto con su cita:** cada idea, tarea y nodo lleva una cita comprobada como texto literal de la transcripción, y el minuto del inicio del segmento que contiene la cita. Las citas que no aparecen en la transcripción se descartan.
- **▶ [mm:ss]:** salta a ese minuto en el audio subido en la sesión.
- **Mapa mental:** se le pide al modelo un árbol de 2 a 4 niveles y de 4 a 8 ramas. Si devuelve menos de 2 ramas (en pruebas reales, Gemini devolvió la raíz vacía), la app arma el mapa desde las ideas clave ya comprobadas: cada idea es una rama y cada cita, una hoja con su minuto.
- **Exportación:** Markdown, Word, Excel, la transcripción en `.txt` y el mapa mental en HTML.
- **Modo local (experimental):** la transcripción corre en la laptop (12.7 min para 64 min de audio en CPU). La estructuración local necesita GPU (en CPU supera los 600 s por bloque); con CPU se recomienda transcribir en local y estructurar en la nube con un modelo ligero.

---

## 5. Why now

1. **La transcripción ya corre en CPU:** modelos modernos de transcripción optimizados en precisión entera (int8) con detección de actividad de voz transcriben una hora de audio en unos 8 a 13 minutos (RTF 0.1336 en clip de 5 min y RTF 0.1969 en reunión de 64 min, 404 MB de RAM), medido en una computadora con procesador AMD Ryzen 5 5600G y 32 GB de RAM, sin GPU (H2, fuente: reunión de trabajo real (no publicada), 64 min, procesada solo en local, y [docs/resultados.md](docs/resultados.md)).
2. **Los modelos de lenguaje devuelven salida estructurada a bajo costo:** con salida estructurada en formato JSON y nivel bajo de razonamiento, estructurar una hora de audio cuesta S/ 0.27 con los precios de 2026 y S/ 0.51 con los de 2027. La cifra se midió en una llamada real y se extrapoló a 1 hora (sección 7).

---

## 6. Demo

- **URL pública:** https://minuta-app.streamlit.app/ (Streamlit Community Cloud). También corre en local.
- **Video de respaldo (60–90 s):** pendiente (enlace por agregar).

### Cómo correrlo

Con Python 3.12:

```powershell
pip install -r requirements.txt
# copia .env.example como .env y completa GEMINI_API_KEY
streamlit run app/streamlit_app.py
```

### Flujo en la app

1. El modo demo está apagado por defecto. El interruptor de arriba muestra un ejemplo precalculado.
2. Elige la plantilla y el modo de análisis "Solo LLM", que es el predeterminado. El detector mmBERT está en desarrollo y no está activo.
3. Sube un audio grabado con el celular.
4. Revisa las notas y la cita de cada punto, y pulsa ▶ [mm:ss] para escuchar ese momento.
5. Exporta el resultado.

### Arquitectura

```mermaid
flowchart LR
    A["Celular: grabadora"] -->|"sube .m4a, .mp3 o .wav"| B["App Streamlit"]
    B --> C["faster-whisper small int8: transcripción con minutos"]
    C --> D{"Proveedor LLM"}
    D -->|"nube"| E["Gemini 3.8 Flash"]
    D -->|"local, experimental"| F["Ollama qwen3:4b"]
    E --> G["Validación de citas literales"]
    F --> G
    G --> H["Notas, mapa mental y exportaciones"]
```

Más detalle en [docs/arquitectura.md](docs/arquitectura.md).

### Modelos y por qué

- **faster-whisper `small` int8:** transcribe una hora en 8 a 13 minutos en CPU, sin GPU (H2, fuente: reunión de trabajo real (no publicada), 64 min, procesada solo en local).
- **Gemini 3.8 Flash (nube):** devuelve JSON que se valida con Pydantic, a un costo medido de S/ 0.27 a S/ 0.51 por hora de audio. El razonamiento va en nivel bajo: con el nivel por defecto, el costo casi se triplicaba.
- **Ollama `qwen3:4b` (local, experimental):** para que el audio y el texto no salgan de la laptop. En CPU dio timeout de > 600 s en la reunión real (H6 falsada: 'transcribe en tu PC; la estructuración local necesita GPU'). La estructuración local completa requiere aceleración por GPU.
- **mmBERT-small:** en desarrollo, no activo en el producto (H4 pendiente).

### Capturas

![Subida de audio](docs/capturas/01-subida.png)
*Vista móvil (390 px): subida de audio y selección de formato.*

![Notas con cita y reproducción](docs/capturas/02-notas.png)
*Vista móvil (390 px): notas con cita literal, distintivo [mm:ss] y términos técnicos.*

![Mapa mental y exportación](docs/capturas/03-mapa.png)
*Escritorio (1280 px): mapa mental interactivo con markmap.js y opciones de exportación.*

---

## 7. Modelo de negocio

**Quién paga:** el universitario que graba sus clases (plan Estudiante) y quien además graba reuniones, charlas o entrevistas (plan Pro).

### Planes

Los precios están por debajo de lo que las 2 personas dijeron estar dispuestas a pagar (S/ 15–25 y S/ 30–40 con uso ilimitado).

| Plan | Precio | Incluye | Costo con uso completo (2026 / 2027) | Margen de contribución (2026 / 2027) |
|---|---|---|---|---|
| Gratis | S/ 0 | 2 h al mes | S/ 0.53 / S/ 1.03 | — (costo de adquisición) |
| Estudiante | S/ 9.90 al mes | 15 h al mes | S/ 3.99 / S/ 7.71 | S/ 5.91 (59.7 %) / S/ 2.19 (22.1 %) |
| Pro | S/ 24.90 al mes | 40 h al mes, modo local y exportaciones | S/ 10.64 / S/ 20.55 | S/ 14.26 (57.3 %) / S/ 4.35 (17.5 %) |

Con todas las horas usadas, el margen es de casi 60 % hoy y de cerca de 20 % en 2027, cuando Google duplica el precio. Bajar el costo por hora es la prioridad: con el detector mmBERT, que filtra el relleno (H5), o con un modelo Flash-Lite.

### Costo por hora de audio

| Precios de Gemini 3.8 Flash | US$ por hora | S/ por hora |
|---|---|---|
| Hasta el 31/12/2026 | 0.0778 | 0.266 |
| Desde el 01/01/2027 | 0.1503 | 0.514 |

- **Precio de Gemini 3.8 Flash** ([aistudio.google.com/docs/pricing](https://aistudio.google.com/docs/pricing), leído el 10/11/2026), por millón de tokens, con la salida que incluye el razonamiento: US$0.75 de entrada y US$3.75 de salida hasta el 31/12/2026, y US$1.50 y US$7.50 desde el 01/01/2027.
- **Tokens por hora (medidos y extrapolados):** 19,186 de entrada y 15,492 de salida, sin razonamiento. Salen de una llamada real sobre la reunión actuada de 346 s, multiplicada por 10.40.
- **Whisper en un servidor (supuesto sin fuente):** US$0.00533 por hora de audio, con 2 vCPU a US$0.040 por hora durante 8 minutos.
- **Tipo de cambio:** 3.418 S/ por US$, venta del sistema bancario SBS al 09/11/2026 ([BCRP, serie PD04640PD](https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04640PD/json/2026-11-01/2026-11-10)).
- El cálculo completo está en [docs/resultados.md](docs/resultados.md), sección 4.

### Competencia

| Alternativa | Qué ofrece y cuánto cuesta | Fuente (leída el 10/11/2026) |
|---|---|---|
| Plaud | Grabadoras NotePin S a US$179 y Note Pro a US$189, marcadas "Agotado" en la sección de comparación. Plan Starter gratis con 300 min al mes, incluido con el aparato; Pro a MXN 167 al mes y Unlimited a MXN 400 al mes, con pago anual. La página mezcla USD y MXN. | [latam.plaud.ai](https://latam.plaud.ai/pages/shop-plaud) |
| Zoom | Plan Básico sin precio indicado, con 3 resúmenes de reuniones y 3 usos de notas con IA al mes. Pro a US$16.99 por usuario al mes con pago mensual, o US$14.16 con pago anual. | [zoom.us/es/pricing](https://zoom.us/es/pricing) |
| NotebookLM | No se citan precios ni límites: no se consultó una fuente oficial. | — |
| No hacer nada | Reescuchar la grabación completa, de 1 a 2 horas. | Conversaciones 01 y 02 |

### Qué sigue

1. La tercera conversación con usuarios.
2. Probar la URL pública desde el celular con audios de 1 hora (H3).
3. Bajar el costo por hora (detector mmBERT o modelo Flash-Lite) y medirlo con audios de 1 hora.
4. Evaluar las tareas (H8) y el mapa mental (H9) con grabaciones reales.

---

## 8. Herramientas del curso

| Herramienta | Dónde está | Por qué esta |
|---|---|---|
| Voz a texto con Whisper (sesión 13) | `minuta/transcribir.py` | faster-whisper `small` int8 transcribe una hora en unos 8 minutos en CPU (H2), sin GPU, y hace posible el modo local. |
| LLMs con salidas estructuradas (sesión 08) | `minuta/esquemas.py`, `minuta/estructurar.py` y `minuta/proveedores.py` | El modelo devuelve JSON con un esquema Pydantic, así que cada punto trae su cita y su minuto, y la app descarta las citas que no están en la transcripción. |

mmBERT afinado (sesión 09, en `entrenamiento/` y `minuta/detector.py`): primer modelo entrenado; F1 macro 0.8217 en datos sintéticos; no activo en la app pública (H4 pendiente).

---

## 9. Qué hizo el agente

- **Claude Code (Claude Opus 5.5):** la investigación, la planificación, las auditorías y las correcciones del 10/11/2026 en `minuta/`, `app/`, `evaluacion/`, la documentación y las dependencias.
- **Un enjambre de Gemini 3.8 Flash en Google Antigravity** construyó la mayor parte del código, con 5 roles:
  - **jefe de proyecto:** coordinación, Git y bitácora;
  - **científico de datos:** datos sintéticos (`entrenamiento/datos/`), oráculos de evaluación (`evaluacion/`) y [docs/resultados.md](docs/resultados.md);
  - **ingeniero de ML:** transcripción (`minuta/transcribir.py` y `minuta/compat.py`), esquemas y estructuración (`minuta/esquemas.py` y `minuta/estructurar.py`) y el afinamiento de mmBERT (`entrenamiento/`);
  - **diseñador UI/UX:** la app (`app/streamlit_app.py`), el mapa mental (`minuta/mapa_html.py`) y las exportaciones (`minuta/exportar.py`);
  - **ingeniero de QA:** `scripts/verificar.py` y las pruebas de extremo a extremo (`tests/e2e/`).
- **El founder:** las decisiones de producto y las conversaciones con usuarios.
- La coautoría con IA se declara en cada commit (`Co-Authored-By`).

### Seguridad y privacidad

- `python scripts/verificar.py` revisa que no haya claves en el historial (`git log -p`), que `.env` no esté versionado y que no haya audio en el índice, y corre la suite de pruebas (`pytest -q`).
- Ningún audio se versiona: las grabaciones de evaluación quedan en `data/privado/`, que está en `.gitignore`.
- La demo precalculada (`data/demo/`) y los fixtures (`data/fixtures/`) son texto ficticio.

### Desarrollo

```powershell
pip install -r requirements-dev.txt
pytest -q
```

Licencia: [MIT](LICENSE).
