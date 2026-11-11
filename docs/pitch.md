# Pitch de 3 minutos: Minuta

- **Presentador:** Rodrigo Norabuena, founder.
- **Formato de la consigna:** 0:00–0:30 problema · 0:30–2:30 demo en vivo · 2:30–3:00 negocio. A los 3:00 se corta y no hay ronda de preguntas.
- **Diapositiva (opcional, una sola):** "Graba. Sube. Vuelve al minuto exacto."
- **Idea de la estructura:** la explicación técnica se dice **mientras la app procesa** (unos 45 s), así la espera no queda en silencio y la demo va de principio a fin.
- **Convención:** lo que va entre corchetes es una acción en pantalla y no se lee.

---

## 0:00–0:30 | Problema

> ¿Cuántos volvieron a la grabación de una sesión solo para encontrar una explicación?
>
> Dos personas que graban sus clases con el celular me respondieron por escrito: graban de una a tres veces por semana y reescuchan grabaciones completas de una a dos horas. Una calcula más de cinco horas para transcribir una reunión. Y una grabadora con IA cuesta hasta 189 dólares.
>
> Soy Rodrigo, y esto es Minuta.

---

## 0:30–2:30 | Demo en vivo con la explicación técnica

> [0:30 · La URL pública ya abierta, con el modo demo apagado.]
> Minuta, en una URL pública. Elijo "Clase" y subo un minuto de clase que grabé con mi celular.
>
> [0:40 · Subir `clip_demo.m4a` y pulsar "Procesar audio con Minuta".]
> Mientras procesa, les cuento qué pasa por dentro.
> Primero, **faster-whisper** transcribe en CPU, sin GPU: una reunión real de 64 minutos tardó 12 minutos.
> Segundo, **Gemini con salida estructurada**: no devuelve texto libre, devuelve JSON que se valida con esquemas de Pydantic.
> Tercero, mi propio control: cada cita tiene que aparecer **palabra por palabra** en la transcripción; si no está, se descarta. El modelo no puede inventar.
>
> [1:25 · Aparecen las notas de clase.]
> Aquí están las notas: cuatro ideas, cada una con su minuto y su cita.
>
> [1:35 · Bajar a "Términos en inglés".]
> Yo dije "JSON" y Whisper escribió "Jason". Primero probé un glosario: mejoró cero puntos. Entonces hice que el modelo detecte el inglés: en 50 términos, el acierto subió de 86 a 98 por ciento.
>
> [1:55 · Pestaña "Mapa mental" y pulsar ▶ en una rama.]
> Mi clase, en un mapa. Un toque y vuelvo a ese minuto del audio.
>
> [2:10 · Descargar el Word.]
> Me lo llevo a Word. Y si la grabación es privada, todo corre en mi laptop con Ollama: nada sale de mi computadora. El código está en GitHub, con 270 pruebas automáticas.

**Plan B, si falla la red, la API o el audio:**
1. Encender el **modo demo** y seguir el mismo guion: muestra un ejemplo precalculado.
2. Si la app no responde, poner el **video de respaldo** (enlace en el README).

---

## 2:30–3:00 | Negocio

> ¿Quién paga? El universitario. Plan Estudiante: 9.90 soles al mes por quince horas; Pro: 24.90 por cuarenta. Una persona dijo que pagaría de 15 a 25 soles; la otra, hasta 40.
>
> Una hora de audio nos cuesta 27 céntimos con los precios de este año: un margen cercano al 60 por ciento. Lo que sigue: probarlo con más estudiantes y bajar ese costo.
>
> Hay muchas herramientas que transcriben. Minuta te devuelve al minuto exacto.

---

## Respaldo de cada cifra (no se lee)

| Lo que digo | Fuente |
|---|---|
| 1–3 veces por semana, 1–2 h, más de 5 h | `docs/research/conversacion-01.md` y `-02.md` |
| Plaud hasta US$ 189 | latam.plaud.ai, leído el 10/11/2026 |
| 64 min transcritos en 12 min | H2, reunión real procesada en local (`docs/resultados.md`) |
| Glosario +0 pts; LLM de 86 % a 98 % | H1 (falsada) y H1b, `evaluacion/terminos_llm.py`, sin pistas de glosario |
| 270 pruebas | `pytest -q` del 11/11/2026 |
| S/ 0.27 por hora, margen ~60 % | `docs/resultados.md`, sección 4 (precios de 2026; en 2027 baja a ~20 %) |
| S/ 15–25 y S/ 30–40 | conversaciones 02 y 01 |

---

## Antes de presentar

- [ ] Tres ensayos con cronómetro. Si a la 1:25 todavía no aparecen las notas, acorta la parte técnica.
- [ ] La URL pública abierta y probada **en una ventana de incógnito** a las 7:00 p. m.
- [ ] `clip_demo.m4a` a mano en la laptop.
- [ ] Procesar el clip una vez antes de empezar, para que Whisper ya esté cargado en el servidor.
- [ ] El interruptor del modo demo funciona (plan B).
- [ ] El video de respaldo abierto en otra pestaña.
