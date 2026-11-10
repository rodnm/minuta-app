# Guion del Pitch de 3 Minutos: Minuta (T41)

**Proyecto:** Minuta — Alternativa económica a Plaud que usa tu celular con mapas mentales interactivos verificables.  
**Presentador:** Rodrigo Norabuena (Founder & Lead Developer).  
**Tiempo Límite:** 3 minutos exactos (a los 3 minutos se corta la presentación según la consigna).  
**Formato:** Presentación en vivo con app Streamlit funcionando desde el navegador y video de respaldo de 60–90 s como plan B.

---

## Estructura Cronometrada (3 Minutos)

### Minuto 0:00 – 1:00 | El Problema y la Oportunidad (60 segundos)

> *"Buenas noches a todos y al jurado de Q-Lab PUCP. Mi nombre es Rodrigo Norabuena.
>
> ¿Alguna vez han salido de una clase de una hora, una reunión de investigación o una entrevista de trabajo con el celular lleno de audios que nunca volvieron a escuchar?
>
> Transcribir y resumir a mano una sola hora de audio toma aproximadamente **cuatro horas de trabajo**, según estimaciones de servicios de transcripción. 
>
> En el mercado existe una solución de hardware llamada **PLAUD Note**, pero cuesta entre **US$ 159 y US$ 189 dólares**, exige cargar un dispositivo físico adicional y cobra suscripciones de hasta **US$ 240 dólares al año** sin precios en soles. 
>
> Por otro lado, herramientas gratuitas como Google NotebookLM generan mapas estáticos en la nube, pero no tienen listas de tareas operativas, no permiten verificar las citas textuales segundo a segundo y no ofrecen un modo privado local.
>
> Además, los transcriptores genéricos fallan sistemáticamente con la jerga técnica: en nuestras mediciones empíricas con audio real, Whisper confundió *arXiv* con *'RCIP'* y *editorial board* con *'digital board'*.
>
> Lo que necesitan es una herramienta que use el teléfono que ya llevan en el bolsillo."*

---

### Minuto 1:00 – 2:00 | La Solución y Demo en Vivo (60 segundos)

> *"Para resolver esto creamos **Minuta**: una alternativa económica a las grabadoras de hardware con IA que convierte las grabaciones de tu celular en transcripciones, resúmenes ejecutivos, listas de tareas y **mapas mentales interactivos verificables**.
>
> Veámoslo funcionando en vivo:
>
> [ACCIÓN EN PANTALLA: Mostrar app Streamlit en pantalla completa o navegador móvil].
>
> Aquí tenemos nuestra aplicación responsiva optimizada para celular. Subimos una grabación o activamos la demo precalculada de una ponencia académica.
>
> En segundos, Minuta genera cuatro salidas estructuradas:
> 1. Primero, un **mapa mental interactivo con markmap.js**: cada nodo representa un concepto jerárquico. Y aquí está nuestro insight clave: **el mapa es 100% verificable**. Cada nodo hijo incluye su minuto exacto y su cita textual literal. Si pulso este botón `▶ [01:15]`, el reproductor salta automáticamente al segundo exacto donde el expositor dijo esa frase.
> 2. Segundo, el **resumen ejecutivo** con ideas clave.
> 3. Tercero, la lista de **acuerdos y to-dos con responsable**, respaldada por citas literales que nuestra validación matemática verifica que cada cita sea literal.
> 4. Y cuarto, exportación directa en un clic a **Markdown, HTML autónomo, Microsoft Word y Excel**.
>
> Si la reunión es confidencial, Minuta cuenta con un modo local que corre con Whisper int8 y Ollama en la laptop sin que un solo byte salga de la máquina."*

---

### Minuto 2:00 – 3:00 | Modelo de Negocio, Costos y Cierre (60 segundos)

> *"Hablemos de los números y el modelo de negocio.
>
> ¿Cuánto nos cuesta procesar una hora de audio?
> Gracias a nuestra arquitectura Map-Reduce con la API de Gemini 3.8 Flash y nuestro detector mmBERT de reducción de relleno, el procesamiento de una hora completa de audio consume aproximadamente 12,000 tokens de transcripción. 
> Esto representa un costo de API de apenas **0.0018 dólares por hora**, es decir, **menos de un centavo de sol (S/ 0.007)**.
>
> Sobre esta estructura de costos ultraligera, definimos tres planes de suscripción en soles:
> 1. **Plan Estudiante (Gratuito):** 3 horas al mes, costo de API de S/ 0.02.
> 2. **Plan Investigador:** S/ 29 soles mensuales por 15 horas de audio, con un margen bruto superior al **99.6%**.
> 3. **Plan Laboratorio / Equipo:** S/ 89 soles mensuales para grupos de investigación y consultores, con un margen bruto superior al **99.5%**.
>
> Frente a los 800 soles que cuesta importar una grabadora Plaud, Minuta entrega una solución accesible en moneda local, respetuosa de la privacidad, verificable matemáticamente y al alcance de cualquier estudiante o investigador con un smartphone.
>
> Muchas gracias. Quedo atento a las preguntas del jurado."*

---

## Lista de Verificación para el Ensayo (HU11)
- [ ] Cronómetro en mano: cortar exactamente a los 2 minutos con 50 segundos para dejar 10 segundos de holgura.
- [ ] Pestaña del navegador abierta con la URL de Minuta en modo demo.
- [ ] Video de respaldo (60–90 s) listo en pestaña adyacente por si falla la conexión en vivo.
- [ ] Citar los fallos reales medidos (*arXiv* → *"RCIP"* y *editorial board* → *"digital board"*).
- [ ] Citar el costo exacto medido por hora: S/ 0.007 soles.
