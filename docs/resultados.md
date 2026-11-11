# Resultados de las hipótesis y costo por hora de audio

- **Startup:** Minuta convierte las clases que los universitarios graban con su celular en notas y un mapa mental donde cada idea lleva su minuto y su cita literal.
- **Método:** hipótesis pre-registradas (H1 a H9), con umbrales fijados antes de ver los datos y oráculos que se corren desde la consola.
- **Fecha de corte:** 10 de noviembre de 2026.
- **Reproducibilidad:**
  - La app llama a los LLM con temperatura 0 (`minuta/proveedores.py`). La generación de datos sintéticos con Gemini usa temperatura 0.4.
  - El generador de sintéticos sin API (`generar_conversacion_sintetica_dry_run`) usa `seed=42`, pero lo mezcla con `hash(tipo)`, y el hash de un texto cambia en cada proceso de Python. Por eso esa generación no es reproducible entre procesos.

---

## 1. Resumen

Minuta responde a un problema que las 2 personas entrevistadas describieron: reescuchan grabaciones completas de 1 a 2 horas para encontrar una explicación. Hoy existen grabadoras con IA como Plaud (NotePin S a US$179 y Note Pro a US$189, marcadas "Agotado" en [latam.plaud.ai](https://latam.plaud.ai/pages/shop-plaud) el 10/11/2026) y herramientas de software como NotebookLM y Zoom AI Notes, que las personas entrevistadas ya usan.

Este documento reúne lo que se midió, lo que falta medir y el costo por hora de audio, medido con una llamada real y extrapolado a 1 hora.

| Estado | Hipótesis |
|---|---|
| Confirmada | H2 (velocidad de Whisper en clip y en reunión real) y H7 (problema real, con n = 2) |
| Falsada | H1 (glosario de términos en inglés) y H6 (Ollama local en CPU: timeout > 600 s) |
| No concluyente | H1b (detección posterior con LLM: mejora +12.0 pts en zona intermedia) |
| Pendiente | H3, H4, H5a, H5b, H8 y H9 |

---

## 2. Matriz de hipótesis

| H# | Hipótesis | Confirmada si | Falsada si | Resultado | Veredicto | Oráculo |
|---|---|---|---|---|---|---|
| **H1** | El glosario ES-EN en la transcripción mejora los términos técnicos en inglés | Recall ≥ 85 % y ≥ +15 pts sobre la línea base (25 frases) | Mejora < 10 pts o recall < 70 % | Línea base: 86 % (43 de 50). Con el glosario del producto (`hotwords`): 86 % (43 de 50). Mejora: **+0 pts**. En un clip continuo de 5 min: 90 % sin glosario y 88 % con `hotwords`. | **FALSADA** | `python -m evaluacion.terminos --audios data/privado/frases/ --modelo small --tipo-glosario producto` |
| **H1b** | Detección posterior de términos en inglés con LLM | Recall ≥ 85 % y ≥ +15 pts sobre la línea base (50 términos) | Mejora < 10 pts o recall < 70 % | Línea base: 86.0 % (43 de 50). Con Gemini Flash: **98.0 %** (49 de 50) o 100.0 % normalizando guiones. Mejora: **+12.0 pts**. Clip demo (`docs/demo/clip_demo.m4a`): detecta JSON transcrito como 'Jason' con 0 descartes. | **NO CONCLUYENTE** | `python -m evaluacion.terminos` + detección estructurada LLM |
| **H2** | `small` int8 con VAD procesa 1 hora de audio en CPU | ≤ 20 min por hora (RTF ≤ 0.33) | > 30 min por hora | Clip 300 s: RTF **0.1336** (8.0 min/h), 404.1 MB RAM. Reunión real (64.42 min, 2,396 segmentos): **12.68 min**, RTF **0.1969**. | **CONFIRMADA** | Fuente: reunión de trabajo real (no publicada), 64 min, procesada solo en local (`evaluacion.privado`); y clip de 300 s (`evaluacion.velocidad`) |
| **H3** | La app cabe en Streamlit Community Cloud | < 2.7 GB de RAM y clip de 60 s en ≤ 60 s | Falla por memoria o > 120 s | Sin desplegar. Whisper `base` usó 225.9 MB de RAM en local. | **PENDIENTE** | Despliegue de prueba y clip de 60 s desde el celular |
| **H4** | mmBERT-small afinado con sintéticos clasifica segmentos y generaliza | F1 macro ≥ 0.70 y recall de `tarea` ≥ 0.80 | F1 macro < 0.55 o recall de `tarea` < 0.65 | Validación interna sobre datos sintéticos retenidos (195 segmentos): **F1 macro 0.8217**, recall de `tarea` **0.6897**, exactitud **82.05 %**. H4 sigue **PENDIENTE** porque sus umbrales pre-registrados exigen una reunión real etiquetada a mano (`data/eval/reunion_etiquetada.csv`). | **PENDIENTE** | `python -m evaluacion.detector --modelo <modelo> --etiquetas data/eval/reunion_etiquetada.csv` |
| **H5a** | El detector ahorra tokens y tiempo en reuniones | −60 % de tokens, −40 % de tiempo y caída del recall de tareas ≤ 5 pts | Ahorro < 40 % o caída > 10 pts | Sin medición: el detector no está entrenado. | **PENDIENTE** | `python -m evaluacion.eficiencia --entrada <reunion.json> --modos solo_llm,detector` |
| **H5b** | El detector ahorra tokens en ponencias | −25 % de tokens y caída de cobertura del mapa ≤ 10 % | Ahorro < 10 % | Sin medición: el detector no está entrenado. | **PENDIENTE** | Ídem, con `<ponencia.json>` |
| **H6** | Ollama `qwen3:4b` devuelve JSON válido, incluido el mapa | ≥ 95 % válido y < 60 s por bloque | < 85 % o > 120 s por bloque | En reunión real de 64 min (6 bloques), el bloque 1 no respondió en 600 s (timeout, 0 de 1 válidos, 0.0 % válido, latencia > 120 s). Limitación: transcribe en tu PC; la estructuración local necesita GPU. | **FALSADA** | Fuente: reunión de trabajo real (no publicada), 64 min, procesada solo en local (`evaluacion.privado`); fixtures en `evaluacion.validez_json` |
| **H7** | El problema es real para quien graba con el celular | ≥ 2 de 3 graban ≥ 2 veces al mes, dedican ≥ 30 min por grabación y no pagarían un aparato como Plaud | 0 o 1 de 3 | 2 de 2 cumplen los 3 criterios, con 2 de las 3 conversaciones requeridas | **CONFIRMADA** (n = 2) | Notas en `docs/research/conversacion-01.md` y `docs/research/conversacion-02.md` |
| **H8** | Las tareas son confiables | Precisión ≥ 0.80, recall ≥ 0.70 y 100 % de citas literales | Precisión < 0.65 o alguna cita no literal | Falta la referencia etiquetada a mano (no hay lista de referencia de la reunión real). | **PENDIENTE** | `python -m evaluacion.todos --pred <salida.json> --ref data/eval/todos_manual.csv` |
| **H9** | El mapa mental es verificable y útil (solo plantilla Clase) | ≥ 90 % de nodos con cita literal, 2–4 niveles, 4–8 ramas en 1 h y mediana de utilidad ≥ 4/5 | < 75 % con cita o mediana < 3/5 | En llamada real con Gemini (T70): 4 ramas y 0 citas descartadas en 19 s. H9 sigue PENDIENTE hasta evaluar la utilidad con usuarios (HU10). | **PENDIENTE** | `python -m evaluacion.mapa --pred <salida.json> --transcripcion <transcripcion.json>` |

---

## 3. Detalle por hipótesis

### 3.1 H1: glosario de términos en inglés (FALSADA)

Se evaluó si un glosario técnico (*hotwords* en Whisper) mejoraba la transcripción de términos en inglés dentro del español (*journal*, *paper*, *grant*, *peer review*, *trade-off*).

Se usaron 25 frases grabadas con el celular (`data/privado/frases/`), con 50 términos esperados:
- **Línea base (sin glosario, `small` int8):** 43 de 50, **recall 86 %**.
- **Con el glosario del producto (`hotwords`):** 43 de 50, **recall 86 %** (**+0 pts**).
- **Clip continuo de 5 minutos (300 s):** 45 de 50 sin glosario (90 %), 45 de 50 con `initial_prompt` (90 %) y 44 de 50 con `hotwords` (88 %).

**Desglose por glosario.** De los 50 términos evaluados, 29 están en el glosario del producto. Ese glosario se versionó un día después del guion de frases, así que esos 29 términos pueden favorecerlo. Se reporta aparte:

| Términos | Sin glosario | Con glosario (`hotwords`) | Cambio |
|---|---|---|---|
| Dentro del glosario (29) | 27 de 29 (93,1 %) | 28 de 29 (96,6 %) | +3,4 pts |
| Fuera del glosario (21) | 16 de 21 (76,2 %) | 15 de 21 (71,4 %) | −4,8 pts |

El glosario ayuda un poco con los términos que contiene y empeora los demás; el efecto neto es 0. Aun con la posible ventaja de los 29 términos, H1 queda falsada. El desglose sale de `python -m evaluacion.terminos` (sección "Desglose por glosario").

Los 7 errores de la línea base:
1. Frase 05: `arXiv` → "RCIP" (*"publicamos una versión preliminar como preprint en RCIP"*).
2. Frase 06: `grant` → "gran" (*"Postulamos a un gran internacional"*).
3. Frase 06: `principal investigator` → "principal investigador".
4. Frase 08: `coauthors` → "co-authors".
5. Frase 11: `editorial board` → "digital board" (*"quedamos a la espera de la digital board"*).
6. Frase 15: `ablation study` → "ablación y study" (*"durante el ablación y study"*).
7. Frase 17: `major revision` → "mayor revision".

**Limitación:** 29 de los 50 términos evaluados ya estaban en el glosario. Falta reportar el recall dentro y fuera del glosario.

**Decisión:** el glosario no mejora el reconocimiento cuando un término en inglés suena casi igual que una palabra en español (*grant* → "gran"). Minuta no promete corregir términos: el LLM no tiene esa instrucción y las citas deben ser literales, así que conservan lo que transcribió Whisper. El error queda a la vista en la cita y se puede escuchar con ▶.

#### 3.1.1 H1b: detección de términos en inglés con LLM (NO CONCLUYENTE)

Como plan B pre-registrado de H1 ante la falsación del glosario en Whisper, se evaluó si el LLM (Gemini Flash) identifica los términos técnicos en inglés a partir de la transcripción cruda de `small` int8 sin glosario, asociando la forma canónica en inglés con el fragmento transcrito.

Se evaluaron las mismas 25 frases (`data/privado/frases/`, 50 términos esperados):
- **Línea base (sin glosario, `small` int8):** 43 de 50, recall 86.00 %.
- **Detección posterior con Gemini Flash:** 49 de 50 (**98.00 %**) comparando texto sin guiones (50 de 50, 100.00 % si se normalizan guiones como en *coauthors* / *co-authors*).
- **Mejora:** **+12.00 pts porcentuales** sobre la línea base.

**Veredicto bajo los umbrales pre-registrados de H1:**
- Confirmada requería: recall ≥ 85 % y mejora ≥ +15 pts. Con una línea base de 86 %, alcanzar +15 pts exigiría 101 % de recall en 50 términos.
- Falsada requería: mejora < 10 pts o recall < 70 %. Al lograr +12.00 pts y 98.00 % de recall, **no queda falsada**.
- Veredicto formal: **NO CONCLUYENTE** (zona intermedia de la regla HDD pre-registrada).

**Prueba en camino real (`docs/demo/clip_demo.m4a`):**
En un clip de clase de 57.2 s, Whisper transcribió *"siguiendo un formato estricto como Jason"*. El pipeline con Gemini Flash identificó el término `JSON` con `transcrito='Jason'`, marca de tiempo `13.92s` y cita literal verificada, con 0 elementos descartados.

---

### 3.2 H2: velocidad de faster-whisper (CONFIRMADA)

Se midió `faster-whisper 1.2.1` con int8 y VAD sobre 300 s de audio real concatenado, en una computadora de escritorio con AMD Ryzen 5 5600G y 32 GB de RAM, sin GPU:

| Modelo | Cuantización | Carga | Transcripción | RTF | Minutos por hora de audio | RAM | Palabras | Veredicto |
|---|---|---|---|---|---|---|---|---|
| `base` | int8 | 0.96 s | 15.09 s | 0.0503 | 3.0 | 225.9 MB | 483 | CONFIRMADA |
| **`small` (elegido)** | int8 | 1.36 s | 40.09 s | **0.1336** | **8.0** | **404.1 MB** | 485 | **CONFIRMADA** |
| `large-v3-turbo` | int8 | 3.69 s | 89.73 s | 0.2991 | 17.9 | 970.4 MB | 486 | CONFIRMADA |

El umbral pedía 1 hora de audio en ≤ 20 minutos (RTF ≤ 0.33). `small` tardó **8.0 minutos por hora** con 404 MB de RAM. El resultado vale para esa computadora; en una laptop más modesta el tiempo puede ser mayor.

**Medición con audio real largo (reunión de 64 min):**
Se procesó una reunión real completa de 64.42 min (2,396 segmentos) con `faster-whisper small int8` en la misma máquina local en CPU:
- Duración del audio: 64.42 min.
- Tiempo de transcripción: 12.68 min.
- RTF observado: **0.1969** (equivalente a 11.8 min por hora de audio).
- Veredicto: **CONFIRMADA** con audio real largo (RTF 0.1969 ≤ 0.33 y 12.68 min ≤ 20 min).

Fuente: reunión de trabajo real (no publicada), 64 min, procesada solo en local.

---

### 3.3 H4: afinamiento de mmBERT-small y validación interna (PENDIENTE)

Se implementó el fine-tuning en CPU de `jhu-clsp/mmBERT-small` para clasificar la intención en segmentos transcritos en 5 clases (`idea`, `tarea`, `acuerdo`, `pregunta`, `relleno`), mitigando el desbalance de clases mediante pesos de pérdida inversamente proporcionales (`WeightedTrainer`).

#### Partición por conversación sin fuga de datos
El dataset sintético (90 conversaciones, 1,351 segmentos con 98.45 % de textos únicos) se dividió agrupando estrictamente **por conversación**, estratificando por tipo (`ponencia`, `reunion`, `entrevista`) con semilla determinista (42):
- **Entrenamiento:** 63 conversaciones (946 segmentos, 70.0 %).
- **Validación:** 14 conversaciones (210 segmentos, 15.5 %).
- **Prueba sintética retenida:** 13 conversaciones (195 segmentos, 14.5 %).
- **Invariante de aislamiento:** cero solapamiento de identificadores de conversación entre las particiones (`train ∩ val = ∅`, `train ∩ test = ∅`, `val ∩ test = ∅`).

#### Entrenamiento en CPU
- Épocas: 3.
- Tamaño de lote: 8.
- Tasa de aprendizaje: 3e-5.
- Longitud máxima (`max_length`): 128 tokens.
- Tiempo de entrenamiento: 543.8 s (~9.06 min en CPU AMD Ryzen 5 5600G).
- Checkpoint final guardado en: `modelos/minuta-detector-mmbert-small/`.

#### Métricas en la prueba sintética retenida (195 segmentos)
- **Exactitud global:** **82.05 %** (160 / 195 aciertos).
- **F1 Macro:** **0.8217**.

| Clase | Precisión | Recall | F1-score | Soporte |
|---|---|---|---|---|
| `idea` | 0.7538 | 0.8750 | 0.8099 | 56 |
| `tarea` | 0.8333 | **0.6897** | 0.7547 | 29 |
| `acuerdo` | 0.7547 | 0.8000 | 0.7767 | 50 |
| `pregunta` | 0.9714 | 0.9444 | 0.9577 | 36 |
| `relleno` | 0.9444 | 0.7083 | 0.8095 | 24 |

**Matriz de confusión (Filas: Real, Columnas: Predicción):**
```text
         idea   tare   acue   preg   rell
 idea       49      1      5      0      1
 tarea       3     20      6      0      0
 acuerd      8      2     40      0      0
 pregun      1      1      0     34      0
 rellen      4      0      2      1     17
```

#### Demostración de clasificación sobre audios y fixtures
Se ejecutó la inferencia del modelo afinado sobre tres fuentes:
1. **Clip demo (`docs/demo/clip_demo.m4a`, 57.2 s, 9 segmentos):**
   - `idea`: 7 segmentos (77.8 %)
   - `pregunta`: 1 segmento (11.1 %)
   - `relleno`: 1 segmento (11.1 %)
   - Segmentos filtrados como relleno: 1 (11.1 %).
2. **Fixture Reunión (`data/fixtures/transcripcion_reunion.json`, 346 s, 40 segmentos):**
   - `idea`: 16 segmentos (40.0 %)
   - `tarea`: 12 segmentos (30.0 %)
   - `acuerdo`: 6 segmentos (15.0 %)
   - `pregunta`: 3 segmentos (7.5 %)
   - `relleno`: 3 segmentos (7.5 %)
   - Segmentos filtrados como relleno: 3 (7.5 %).
3. **Fixture Ponencia (`data/fixtures/transcripcion_ponencia.json`, 432 s, 40 segmentos):**
   - `idea`: 34 segmentos (85.0 %)
   - `tarea`: 1 segmento (2.5 %)
   - `acuerdo`: 0 segmentos (0.0 %)
   - `pregunta`: 3 segmentos (7.5 %)
   - `relleno`: 2 segmentos (5.0 %)
   - Segmentos filtrados como relleno: 2 (5.0 %).

**Estado formal de H4:** Aunque el F1 macro en datos sintéticos (**0.8217**) supera el umbral de 0.70 y el modelo demuestra capacidad de discriminación acorde al tipo de contenido (alta concentración de tareas en reunión y de ideas en ponencia), **H4 sigue formalmente PENDIENTE** porque su criterio pre-registrado exige contrastación sobre una reunión real de trabajo etiquetada a mano (`data/eval/reunion_etiquetada.csv`), sin sustituir datos sintéticos por datos reales.

---

### 3.4 H5a y H5b: ahorro con el detector (PENDIENTE)

No hay medición. El detector mmBERT entrenado no está activo en la app pública para evitar la sobrecarga de dependencias pesadas (PyTorch) en Streamlit Community Cloud. La app desplegada opera en modo "Solo LLM".

---

### 3.5 H6: salida estructurada local con Ollama (FALSADA)

Se evaluó `qwen3:4b` en Ollama (`temperature=0.0`, `think=false`) en dos escenarios:
1. **Fixtures cortos:** 2 de 2 bloques válidos (100 %) con 64.09 s por bloque en promedio.
2. **Reunión real completa de 64 min (6 bloques):** en el bloque 1, `qwen3:4b` no respondió en 600 s (timeout configurado), con 0 de 1 bloques válidos (0.0 % de JSON válido) y latencia superior a los 120 s del umbral de falsación.

Fuente: reunión de trabajo real (no publicada), 64 min, procesada solo en local.

**Decisión y limitación declarada:** H6 queda **FALSADA** para estructuración en CPU. Siguiendo el plan pre-registrado y sin re-medir con 8b (que aumentaría la carga en CPU), se declara la limitación del modo local en CPU:
> *"transcribe en tu PC; la estructuración local necesita GPU"*

Whisper int8 resuelve la transcripción en local en CPU (H2 confirmada), mientras que la estructuración del mapa y notas requiere aceleración por GPU local o la API en la nube (Gemini Flash).

---

### 3.6 H7: problema real (CONFIRMADA, n = 2)

Hay notas de 2 de las 3 conversaciones requeridas (`docs/research/conversacion-01.md` y `docs/research/conversacion-02.md`).

| Criterio pre-registrado | Persona 1 (conversación 01) | Persona 2 (conversación 02) | ¿Se cumple? |
|---|---|---|---|
| Graba con el celular ≥ 2 veces al mes | "ahora es 1-3 veces por semana" | "Será unas 1 a 2 veces por semana" | Sí, en ambas |
| Dedica ≥ 30 min por grabación a repaso o apuntes | "Si dura 1-2 horas lo voy a escuchar nuevamente" | "usualmente hago grabaciones de 2 horas de mis clases y las escucho completas" | Sí, en ambas |
| No pagaría un aparato como Plaud | "prefiero pagar una suscripción que use a mi celular como grabadora" | "No pagaría porque es una inversión fuerte" | Sí, en ambas |

- **Veredicto:** CONFIRMADA (2 de 2 cumplen los 3 criterios).
- **Limitaciones:** n = 2, respuestas por escrito y contactos del founder. Falta la tercera conversación.
- **Con qué se comparan:** con software, no con un aparato. La persona 1 valoró la prueba gratuita de 3 usos de Zoom AI Notes. La persona 2 usa NotebookLM y escribió que "no siempre recoge con precisión algunos términos técnicos o palabras en inglés". También escribió: "si estoy apurada voy momento exacto donde quiero escuchar nuevamente la explicación".

---

### 3.7 H8 y H9: tareas y mapa mental (PENDIENTES)

- **H8 (tareas):** falta una reunión transcrita y etiquetada a mano. Las pruebas unitarias comprueban que el contrato descarta las citas que no aparecen en la transcripción.
- **H9 (mapa mental):** aplica solo a la plantilla **Ponencia / Clase / Charla**. En la llamada real con Gemini (T70) sobre la transcripción de clase se obtuvieron 4 ramas principales y 0 citas descartadas en 19 s. H9 sigue **PENDIENTE** hasta completar la evaluación de utilidad con usuarios (HU10).

---

## 4. Costo por hora de audio

### 4.1 Supuestos y precios

Los tokens se **midieron** con el `usageMetadata` de una llamada real del 10/11/2026. Se usó el fixture de la reunión actuada (`data/fixtures/transcripcion_reunion.json`, 346 s) con la plantilla Reunión y el razonamiento en nivel `low`. Respondió `gemini-3.6-flash`, el modelo de respaldo, que tiene el mismo precio que 3.8 Flash. La llamada tardó 27 s.

Medido: **1,844 tokens de entrada, 1,489 de salida y 0 de razonamiento.** La hora se extrapola linealmente: × 3600 / 346 = × 10.40.

| Dato | Valor | Tipo | Fuente o base |
|---|---|---|---|
| Tokens de entrada por hora de audio | 19,186 | extrapolado de una medición | 1,844 tokens en 346 s × 10.40 |
| Tokens de salida por hora de audio, con razonamiento | 15,492 | extrapolado de una medición | 1,489 tokens en 346 s × 10.40, con 0 de razonamiento |
| Whisper en un servidor | US$0.00533 por hora de audio | supuesto sin fuente | 2 vCPU a US$0.040 por hora durante 8 min (los 8 min vienen de H2) |
| Gemini 3.8 Flash, entrada, por 1M de tokens | US$0.75 hasta el 31/12/2026; US$1.50 desde el 01/01/2027 | oficial | [aistudio.google.com/docs/pricing](https://aistudio.google.com/docs/pricing), leído el 10/11/2026 |
| Gemini 3.8 Flash, salida (incluye razonamiento), por 1M de tokens | US$3.75 hasta el 31/12/2026; US$7.50 desde el 01/01/2027 | oficial | Ídem |
| Tipo de cambio | 3.418 S/ por US$ | oficial | SBS, venta del sistema bancario, 09/11/2026 (el 10/11 aún no estaba publicado): [BCRP, serie PD04640PD](https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04640PD/json/2026-11-01/2026-11-10) |

**Por qué el razonamiento va en `low`.** Con el nivel por defecto (`medium`), la misma reunión gastó 4,030 tokens de razonamiento además de 1,853 de respuesta, y tardó 233 s. El razonamiento se cobra como salida, así que con `medium` el costo por hora casi se triplicaba. El nivel `low` es el mínimo que acepta `gemini-3.8-flash` ([aistudio.google.com/docs/thinking](https://aistudio.google.com/docs/thinking)).

**Límites de la medición:**
- Es una sola corrida, sobre una reunión actuada.
- La extrapolación a 1 hora supone que el costo crece en proporción a la duración.
- Whisper en un servidor sigue siendo un supuesto.

### 4.2 Cálculo

| Concepto | Precios 2026 | Precios 2027 |
|---|---|---|
| Entrada del LLM (19,186 tokens) | US$0.01439 | US$0.02878 |
| Salida del LLM (15,492 tokens) | US$0.05810 | US$0.11619 |
| Whisper en un servidor (supuesto) | US$0.00533 | US$0.00533 |
| **Total por hora de audio** | **US$0.0778** | **US$0.1503** |
| **Total en soles (× 3.418)** | **S/ 0.266** | **S/ 0.514** |

En el modo local, Whisper y el LLM corren en la laptop del usuario, y la empresa no paga esa hora.

---

## 5. Planes y margen de contribución

Los precios están por debajo de lo que las 2 personas dijeron estar dispuestas a pagar (S/ 15–25 y S/ 30–40 con uso ilimitado). El costo y el margen suponen que el usuario consume todas sus horas.

| Plan | Precio | Horas al mes | Costo (2026 / 2027) | Margen de contribución (2026 / 2027) | Por qué |
|---|---|---|---|---|---|
| **Gratis** | S/ 0 | 2 | S/ 0.53 / S/ 1.03 | — (costo de adquisición) | La persona 1 valoró la prueba gratuita de 3 usos de Zoom. |
| **Estudiante** | S/ 9.90 al mes | 15 | S/ 3.99 / S/ 7.71 | S/ 5.91 (59.7 %) / S/ 2.19 (22.1 %) | Para universitarios que graban 1 a 2 veces por semana. |
| **Pro** | S/ 24.90 al mes | 40, con modo local y exportaciones | S/ 10.64 / S/ 20.55 | S/ 14.26 (57.3 %) / S/ 4.35 (17.5 %) | Dentro del rango de S/ 15–25 de la persona 2. |

Con todas las horas usadas, el margen es de casi 60 % con los precios de 2026 y baja a cerca de 20 % con los de 2027, cuando Google duplica el precio. Dos palancas para bajar el costo, todavía sin medir:
- el detector mmBERT, que filtraría el relleno antes del LLM (H5a y H5b);
- un modelo Flash-Lite.

---

## 6. Competencia

Precios leídos el 10/11/2026 en las páginas oficiales:

| Alternativa | Qué ofrece y cuánto cuesta | Fuente |
|---|---|---|
| Plaud | Grabadoras NotePin S a US$179 y Note Pro a US$189, marcadas "Agotado" en la sección de comparación. Plan Starter gratis con 300 min al mes, incluido con el aparato; Pro a MXN 167 al mes y Unlimited a MXN 400 al mes, con pago anual. La página mezcla USD y MXN. | [latam.plaud.ai/pages/shop-plaud](https://latam.plaud.ai/pages/shop-plaud) |
| Zoom | Plan Básico sin precio indicado, con 3 resúmenes de reuniones y 3 usos de notas con IA al mes. Pro a US$16.99 por usuario al mes con pago mensual, o US$14.16 con pago anual. | [zoom.us/es/pricing](https://zoom.us/es/pricing) |
| NotebookLM | No se citan precios ni límites: no se consultó una fuente oficial. | — |
| No hacer nada | Reescuchar la grabación completa, de 1 a 2 horas. | Conversaciones 01 y 02 |

Los "3 usos" de la persona 1 coinciden con la cuota del plan Básico de Zoom.

**Lo que ofrece Minuta:** usa el celular que ya se tiene, cobra en soles, da un formato por tipo de grabación (notas de clase con mapa mental, notas de reunión o esquema por temas) y pone en cada punto una cita comprobada como texto literal de la transcripción, con el minuto del inicio del segmento que la contiene.

---

## 7. Margen de contribución por plan (precios de 2027)

```mermaid
flowchart LR
    subgraph Plan_Estudiante["Plan Estudiante (S/ 9.90 al mes)"]
        direction TB
        PE["Ingreso: S/ 9.90"]
        CE["Costo de 15 h: S/ 7.71"]
        ME["Margen: S/ 2.19 (22.1 %)"]
        PE --> CE --> ME
    end

    subgraph Plan_Pro["Plan Pro (S/ 24.90 al mes)"]
        direction TB
        PP["Ingreso: S/ 24.90"]
        CP["Costo de 40 h: S/ 20.55"]
        MP["Margen: S/ 4.35 (17.5 %)"]
        PP --> CP --> MP
    end
```

---

## 8. Conclusiones para el pitch

1. **El celular basta:** las 2 personas graban con su celular y no comprarían un aparato como Plaud (US$179–189).
2. **El glosario no resolvió los términos en inglés (H1 falsada):** Whisper acertó 43 de 50 términos (86 %) con o sin glosario. Minuta no promete corregirlos; la cita literal deja el error a la vista.
3. **Cada punto con su cita:** la persona 2 busca a mano el minuto de una explicación. En Minuta, cada punto lleva una cita comprobada como texto literal de la transcripción y el inicio del segmento que contiene la cita.
4. **El margen es positivo pero estrecho:** una hora de audio cuesta S/ 0.27 con los precios de 2026 y S/ 0.51 con los de 2027, medido y extrapolado. Con todas las horas usadas, el margen es de casi 60 % hoy y de cerca de 20 % en 2027. Bajar el costo por hora es la prioridad de negocio.
