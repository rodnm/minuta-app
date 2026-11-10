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
> En el mercado existe una solución de hardware llamada **PLAUD Note**, pero cuesta entre **US$ 159 y US$ 189 dólares**, exige cargar un dispositivo físico adicional y cobra suscripciones anuales sin precios en soles. 
>
> Por otro lado, herramientas como Google NotebookLM o Zoom AI Notes no permiten verificar las citas textuales segundo a segundo con audio enlazado, no ofrecen to-dos con responsable ni disponen de un modo privado local.
>
> Además, los transcriptores genéricos fallan sistemáticamente con la jerga técnica: en nuestras mediciones empíricas con audio real, Whisper confundió *arXiv* con *'RCIP'* y *editorial board* con *'digital board'*.
>
> Las 2 personas con las que hablé graban cada semana clases de 1 a 2 horas y las vuelven a escuchar completas. Ninguna compraría un Plaud: ya usan Zoom AI Notes o NotebookLM. Lo que necesitan es una herramienta que use el teléfono que ya llevan en el bolsillo."*

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
> En segundos, Minuta genera el formato adecuado para cada grabación:
> 1. Para ponencias y clases: **Notas de clase con mapa mental interactivo** en markmap.js. Cada nodo hijo incluye su minuto exacto y su cita textual literal. Como me dijo una de las personas entrevistadas: *'si estoy apurada voy momento exacto donde quiero escuchar nuevamente la explicación'*. Si pulso este botón `▶ [01:15]`, el reproductor salta automáticamente al segundo exacto donde se pronunció esa frase.
> 2. Para reuniones: **Notas de reunión** con resumen, temas, acuerdos y **to-dos con responsable y fecha límite**, respaldados por citas verificadas (sin mapas mentales innecesarios).
> 3. Para entrevistas: **Esquema por temas** estructurado en lista jerárquica con minuto y cita en cada punto, más libro de códigos.
> 4. Y en todas las plantillas: la transcripción completa y exportación en un clic a **Markdown, Microsoft Word, Excel y texto plano**.
>
> Si la reunión es confidencial, Minuta cuenta con un modo local que corre con Whisper int8 y Ollama en la laptop sin que un solo byte salga de la máquina."*

---

### Minuto 2:00 – 3:00 | Modelo de Negocio, Costos y Cierre (60 segundos)

> *"Hablemos de los números y el modelo de negocio.
>
> ¿Cuánto nos cuesta procesar una hora de audio?
> Sumando la transcripción acústica con faster-whisper (8 minutos de CPU) y la estructuración contextual con la API de Gemini 2.5 Flash a precios vigentes, el procesamiento de una hora completa de audio nos cuesta apenas **0.017 dólares, es decir, unos 6 céntimos de sol (S/ 0.064)**.
>
> Sobre esta estructura unitaria sostenible, definimos tres planes en soles alineados con lo que los usuarios indicaron pagar:
> 1. **Plan Gratis:** 2 horas al mes para probar el producto sin costo (inversión de adquisición de apenas S/ 0.13).
> 2. **Plan Estudiante:** S/ 9.90 soles al mes por 15 horas de audio, con un margen de contribución del **90%** (+S/ 8.94 al mes).
> 3. **Plan Pro:** S/ 24.90 soles al mes por 40 horas con modo local y exportaciones, dentro del rango de 15 a 25 soles indicado por los usuarios, con un margen del **90%** (+S/ 22.34 al mes).
>
> Frente a los más de 600 soles que cuesta importar una grabadora Plaud, Minuta entrega una solución accesible en moneda local, respetuosa de la privacidad, verificable matemáticamente y al alcance de cualquier estudiante o investigador con un smartphone.
>
> Muchas gracias. Quedo atento a las preguntas del jurado."*

---

## Lista de Verificación para el Ensayo (HU11)
- [ ] Cronómetro en mano: cortar exactamente a los 2 minutos con 50 segundos para dejar 10 segundos de holgura.
- [ ] Pestaña del navegador abierta con la URL de Minuta en modo demo.
- [ ] Video de respaldo (60–90 s) listo en pestaña adyacente por si falla la conexión en vivo.
- [ ] Citar los fallos reales medidos (*arXiv* → *"RCIP"* y *editorial board* → *"digital board"*).
- [ ] Citar el costo exacto medido por hora: S/ 0.064 soles.
