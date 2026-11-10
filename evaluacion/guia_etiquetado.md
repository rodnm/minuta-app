# Guía Metodológica de Etiquetado Humano (Minuta)

Esta guía establece las directrices estandarizadas para la anotación manual de segmentos de audio transcritos correspondientes a reuniones de trabajo o ponencias académicas (tarea **HU06**). El objetivo es construir el conjunto de referencia (*ground truth*) para evaluar la generalización del detector multiclase (**hipótesis H4**) y la fidelidad de extracción de to-dos (**hipótesis H8**).

---

## 1. Principios Generales

1. **Objetividad y contexto:** La etiqueta debe representar la función discursiva principal del segmento dentro del flujo de la conversación, no la apreciación subjetiva del anotador.
2. **Anonimato y privacidad (L21, L25):** En caso de mencionar entidades en transcripciones o ejemplos, emplear términos genéricos ("escuela de negocios", "universidad pública", "organismo internacional") y nombres de oradores ficticios ("Andrea", "Carlos", "Lucía", "Profesor").
3. **Exclusividad mutua:** Cada segmento recibe exactamente una de las cinco clases predefinidas.

---

## 2. Taxonomía de Clases

Las cinco clases del detector son:

### 2.1 `idea`
- **Definición:** Conceptos, hipótesis, antecedentes contextuales, explicaciones técnicas, propuestas conceptuales o reflexiones temáticas que transmiten conocimiento sustantivo pero no configuran un compromiso de acción inmediata ni una decisión pactada.
- **Ejemplos:**
  - *"Las políticas de acceso abierto de este publisher contemplan la exención parcial del pago de APC para países en desarrollo."*
  - *"Una arquitectura map-reduce por bloques de diez minutos reduce el riesgo de alucinaciones en el resumen largo."*
  - *"Considero que contrastar nuestra propuesta frente a soluciones propietarias como Plaud aportará valor al paper."*

### 2.2 `tarea`
- **Definición:** Compromiso de acción concreta asignada a una persona específica o autoasignada por un miembro del equipo, con plazo explícito, implícito o relativo ("para el viernes", "mañana", "el próximo lunes"). Corresponde a un elemento accionable de *to-do*.
- **Ejemplos:**
  - *"Andrea, por favor empaqueta el dataset y documenta el data card en Hugging Face antes del viernes."*
  - *"Yo configuraré el script verificar.py con las comprobaciones de pytest y seguridad de credenciales para el lunes."*
  - *"Me encargo de redactar el borrador completo de introducción y metodología a más tardar el 18 de noviembre."*

### 2.3 `acuerdo`
- **Definición:** Decisión firme adoptada por consenso o determinación explícita del grupo. Cierra una discusión o fija una directriz formal que rige el trabajo futuro.
- **Ejemplos:**
  - *"Queda acordado que ninguna credencial ni archivo .env se versionará en el repositorio público."*
  - *"Acordamos dejar la API de Gemini como proveedor predeterminado y Ollama como opción offline."*
  - *"Fijamos la siguiente sesión de sincronización para el jueves a las cuatro de la tarde vía videoconferencia."*

### 2.4 `pregunta`
- **Definición:** Interrogantes formuladas para indagar información, solicitar aclaración técnica o abrir una deliberación ante el expositor o el equipo de trabajo.
- **Ejemplos:**
  - *"¿Qué criterios recomiendan para seleccionar entre un journal Q1 con APC alto y un journal Q2 sin cobro?"*
  - *"¿Cómo podemos saber si una revista invitada por correo electrónico califica como publisher predatorio?"*
  - *"¿Cuál es el tiempo promedio aceptable que debería demorar el primer dictamen de peer review?"*

### 2.5 `relleno`
- **Definición:** Expresiones de cortesía mecánica, pruebas de conectividad o audio, muletillas extensas, saludos/despedidas formales, interrupciones logísticas o charla informal sin contenido temático sustantivo.
- **Ejemplos:**
  - *"Hola, probando audio, ¿me escuchan bien al fondo de la sala?"*
  - *"Bueno, eh, sí, claro, o sea, pasemos a lo siguiente."*
  - *"¿Alguien podría compartirme el cargador del celular por favor?"*
  - *"Muchas gracias a todos por conectarse, que tengan buena tarde."*

---

## 3. Criterios de Desempate y Jerarquía de Precedencia

Cuando un segmento contiene múltiples intenciones o elementos limítrofes, aplique la siguiente jerarquía de precedencia:

1. **`tarea` prevalece sobre `idea` y `pregunta` retórica:** Si un enunciado plantea una sugerencia pero culmina en una asignación operativa concreta ("Sería conveniente revisar el código, Carlos tú lo haces mañana"), se etiqueta como `tarea`.
2. **`acuerdo` prevalece sobre `idea`:** Si una formulación conceptual es adoptada formalmente como directriz del equipo ("Por lo tanto, resolvemos no admitir audios mayores a dos horas"), se etiqueta como `acuerdo`.
3. **`pregunta` genuina vs. solicitud de acción:** Si una pregunta busca delegar una acción ("¿Andrea, podrías enviar el correo hoy?"), clasifique como `tarea` si el contexto refleja aceptación o delegación directa de responsabilidad. Si es una duda abierta sobre viabilidad ("¿Podríamos eventualmente usar Docker?"), clasifique como `pregunta`.
4. **`relleno` vs. `idea` breve:** Si un segmento aporta únicamente marcadores discursivos ("exacto", "de acuerdo", "bien"), clasifique como `relleno`. Solo si expresa un consenso formal sobre un tema clave se eleva a `acuerdo`.

---

## 4. Instrucciones Operativas para la Plantilla CSV

1. Abrir el archivo `data/eval/plantilla_etiquetado.csv` (o duplicarlo como `data/eval/reunion_etiquetada.csv`).
2. Mantener intactas las columnas:
   - `id`: Identificador numérico secuencial del segmento (1, 2, 3...).
   - `inicio_s`: Marca de tiempo inicial en segundos (ej. `0.0`, `12.5`).
   - `fin_s`: Marca de tiempo final en segundos (ej. `12.5`, `25.0`).
   - `orador`: Nombre ficticio o rol del orador (ej. `Carlos`, `Andrea`, `Moderador`).
   - `texto`: Texto literal transcrito del segmento.
   - `etiqueta_humana`: Únicamente uno de los cinco valores exactos en minúsculas:
     - `idea`
     - `tarea`
     - `acuerdo`
     - `pregunta`
     - `relleno`
3. Guardar el archivo en codificación `UTF-8` con saltos de línea estándar (`\n`) y sin comillas innecesarias.

---

## 5. Verificación de Calidad

Antes de ejecutar los arneses de evaluación:
- Comprobar que no existan valores vacíos en `etiqueta_humana`.
- Validar que no haya espacios en blanco sobrantes (por ejemplo `"tarea "` en vez de `"tarea"`).
- Verificar que la proporción de `tarea` en reuniones sea al menos del 6% y `relleno` al menos del 10% para garantizar representatividad estadística.
