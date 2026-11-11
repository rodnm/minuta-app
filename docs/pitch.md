# Pitch de 3 minutos: Minuta

- **Presentador:** Rodrigo Norabuena, founder.
- **Formato de la consigna:** 0:00–0:30 problema, 0:30–2:30 demo en vivo, 2:30–3:00 negocio. A los 3:00 se corta y no hay ronda de preguntas.
- **Diapositiva (opcional, una sola):** el one-liner.
- **Texto hablado:** 326 palabras (70 + 183 + 73). Lo que va entre corchetes es una acción en pantalla y no se lee.

---

## 0:00–0:30 | Problema (texto hablado: 70 palabras)

> Soy Rodrigo Norabuena, founder de Minuta. Dos personas que graban sus clases con el celular me respondieron por escrito. Cada semana graban de una a tres veces, y después reescuchan grabaciones completas de una a dos horas para encontrar una explicación. Una calcula más de cinco horas para transcribir una reunión. Una grabadora con IA como Plaud cuesta entre 179 y 189 dólares, y ninguna de las dos la compraría.

---

## 0:30–2:30 | Demo en vivo (texto hablado: 183 palabras)

> [Mostrar la app en la laptop, con el modo demo apagado.]
> Esta es Minuta, corriendo en mi laptop. El modo demo está apagado: lo que van a ver se procesa ahora.
>
> [Elegir la plantilla Ponencia / Clase / Charla y el modo "Solo LLM". Subir el clip.]
> Elijo la plantilla de clase y el modo Solo LLM, y subo un clip de veinticinco segundos que grabé con mi celular. Mientras procesa: Whisper transcribe el audio en esta laptop, y Gemini 3.8 Flash arma las notas con salida estructurada.
>
> [Mostrar las notas de clase y el mapa mental.]
> Aquí están las notas: resumen, ideas clave y el mapa mental. Cada idea trae su minuto y una cita, y la app comprueba que la cita esté, palabra por palabra, en la transcripción. Si no está, la descarta. Como me escribió una de ellas: "si estoy apurada voy momento exacto donde quiero escuchar nuevamente la explicación".
>
> [Pulsar ▶ en una idea.]
> Pulso aquí y el audio salta al inicio del segmento que contiene esa cita.
>
> [Abrir la exportación.]
> Exporto a Word, Excel o Markdown, el mapa en HTML y la transcripción completa. Para reuniones hay notas con tareas y responsables, y para entrevistas, un esquema por temas. Y si la grabación es privada, hay un modo local experimental con Ollama: el audio y el texto no salen de la laptop.

**Plan B**, si falla la red, la API o el audio:
1. Encender el modo demo, que muestra un ejemplo precalculado, y seguir el mismo guion.
2. Si la app no responde, poner el video de respaldo (enlace en el README).

---

## 2:30–3:00 | Negocio (texto hablado: 73 palabras)

> ¿Quién paga? El universitario. El plan Estudiante cuesta 9.90 soles al mes por quince horas, y el Pro, 24.90 por cuarenta horas, con modo local. Una escribió que pagaría de 15 a 25 soles; la otra, de 30 a 40 con uso ilimitado. Estimamos que una hora de audio nos cuesta unos 17 céntimos con los precios de 2027: margen cerca de 75 %. Lo que sigue: la tercera conversación y la URL pública.

---

## Antes de presentar

- [ ] Ensayar con cronómetro. Cortar en 2:50 para tener 10 segundos de holgura.
- [ ] Abrir la app en la laptop con `GEMINI_API_KEY` en `.env` y procesar el clip una vez antes de empezar.
- [ ] Tener el clip de 20 a 30 segundos en la laptop, grabado con el celular.
- [ ] Comprobar que el modo demo arranca apagado y que el interruptor funciona, para el plan B.
- [ ] Tener abierto el video de respaldo en otra pestaña.
