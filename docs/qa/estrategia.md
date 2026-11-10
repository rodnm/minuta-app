# Estrategia Integral de Aseguramiento de Calidad (QA) — Minuta

**Proyecto:** Minuta (Startup Diplomatura Q-Lab PUCP)  
**Rol responsable:** Senior QA Engineer (`qa`)  
**Referencias normativas:** `odd/tasks/minuta.md` (S1–S16, H1–H9), `docs/plan/plan-maestro.md`, `docs/plan/roles.md`

---

## 1. Principios Rectores y Filosofía de QA

El aseguramiento de calidad en **Minuta** opera bajo el principio de **verificación con evidencia estricta y no por confianza**. Cada afirmación sobre funcionalidad, seguridad o rendimiento debe estar respaldada por un comando ejecutable, una prueba automatizada o un registro observable.

Las metas fundamentales son:
1. **Garantizar la privacidad absoluta (Regla L21):** Ningún archivo de audio se almacena en el servidor ni se versiona en Git.
2. **Cero fugas de credenciales:** Escaneo estricto y continuo de secretos en el árbol de trabajo y en el historial de Git (`git log -p`).
3. **Validación científica mediante HDD:** Las hipótesis experimentales (H1 a H9) cuentan con oráculos deterministas pre-registrados con umbrales inmutables.
4. **Construcción ágil y disciplinada mediante ODD:** Desarrollo guiado por el documento de feature (`odd/tasks/minuta.md`), ciclo Test-First (RED → GREEN → Refactor) y unidades de cambio revisables (≤ ~400 líneas).

---

## 2. La Pirámide de Pruebas de Minuta

La arquitectura de pruebas está estructurada en tres niveles para maximizar la cobertura, minimizar el tiempo de ejecución y asegurar retroalimentación inmediata:

```text
                  ▲
                 / \
                /   \     E2E / Humo (Streamlit AppTest)
               /     \    tests/e2e/test_smoke.py
              /-------\
             /         \   Integración y Oráculos HDD
            /           \  evaluacion/*.py (H1-H9, CLI reproducible)
           /-------------\
          /               \ Pruebas Unitarias de Contrato y Componentes
         /_________________\ tests/unit/test_*.py (Pydantic v2, mocks deterministas)
```

### 2.1 Nivel 1: Pruebas Unitarias (Base de la Pirámide)
- **Ubicación:** `tests/unit/test_*.py`
- **Enfoque:** Validación exhaustiva del contrato de datos Pydantic v2 (`minuta/esquemas.py`), funciones de apoyo, parseo y formato.
- **Aislamiento:** No realizan llamadas a APIs externas en vivo ni descargan modelos pesados. Utilizan fixtures locales (`data/fixtures/*.json`) y proveedores simulados deterministas.
- **Contratos congelados:** Todo cambio estructural en `NodoMapa`, `MapaMental`, citas de `Evidencia` o plantillas requiere validación cruzada antes de su integración.

### 2.2 Nivel 2: Arneses de Evaluación y Oráculos HDD (Nivel Medio)
- **Ubicación:** `evaluacion/*.py` y `tests/unit/test_evaluacion_*.py`
- **Enfoque:** Medición cuantitativa de las hipótesis pre-registradas (H1: glosario ES-EN, H2: velocidad Whisper, H4: detector mmBERT, H5: ahorro de tokens, H6: validez JSON en Ollama, H8: precisión to-do, H9: mapa mental con evidencia).
- **Determinismo:** Semillas fijas (`seed=42`), temperatura 0.0 en LLMs y reporte de métricas estándar (recall, F1 macro, RTF, porcentaje de validez).

### 2.3 Nivel 3: Pruebas de Humo de Extremo a Extremo (Cúspide de la Pirámide)
- **Ubicación:** `tests/e2e/test_smoke.py`
- **Enfoque:** Simulación e2e de la aplicación Streamlit mediante `streamlit.testing.v1.AppTest`.
- **Alcance verificado:**
  - Inicialización sin excepciones en modo demo.
  - Conmutación dinámica entre plantillas (*Ponencia / Clase / Charla*, *Reunión*, *Entrevista*).
  - Interactividad del reproductor: clic en botones de marcas de tiempo `▶ [mm:ss]` y actualización de posición temporal en sesión.
  - Reactividad de controles táctiles (*mobile-first*), caja de glosario y conmutador de modo demo.

---

## 3. Metodología ODD: Test-First y Superficies Acotadas

1. **Ciclo RED → GREEN → Refactor:** Antes de implementar la lógica funcional de una tarea, se define la prueba unitaria o arnés que verifique el comportamiento esperado. Se comprueba el fallo inicial (RED), se escribe la implementación mínima (GREEN) y se procede a la optimización.
2. **Superficies de Edición Estrictas (`Allowed edit surfaces`):** Cada perfil del enjambre edita únicamente los archivos bajo su dominio. QA edita exclusivamente `tests/e2e/**`, `scripts/verificar.py` y `docs/qa/**`, protegiendo la integridad del código fuente de producción.
3. **Líneas de Riesgo (`Risk lines`):** Cada entrega se califica con su nivel de riesgo inherente:
   - *Passive:* Documentación o activos estáticos (revisión estructural).
   - *Medium:* Cambios ordinarios de comportamiento con pruebas focalizadas.
   - *High:* Datos irreversibles, seguridad/claves, contratos externos o despliegue en la nube (requiere verificación independiente de QA).

---

## 4. Seguridad, Privacidad y Regla L21

La privacidad es una propuesta de valor central de Minuta frente a competidores en la nube:
- **Regla de Privacidad L21:** Está terminantemente prohibido versionar o subir archivos de audio (`*.m4a`, `*.mp3`, `*.wav`, `*.ogg`, `*.webm`, `*.aac`). Todo audio de prueba o evaluación reside en `data/privado/`, la cual está ignorada en `.gitignore`.
- **Rastreo en Git:** El script `scripts/verificar.py` bloquea cualquier commit o validación si detecta archivos `.env` o extensiones de audio en el índice de Git (`git ls-files`).
- **Escaneo de Credenciales:** Búsqueda automatizada de claves API reales (`AIza...`, `sk-...`, `ghp_...`, llaves privadas RSA/SSH, AWS tokens) tanto en los archivos rastreados del árbol como en el historial completo de commits (`git log -p`).

---

## 5. Verificación Independiente de Despliegue (Puerta 3)

Como parte de la mitigación de riesgos de alto impacto (Riesgo 5: Despliegue, Riesgo 2: Claves), QA actúa como verificador independiente:
1. **Prueba de Humo en URL Pública:** Verificación de la aplicación desplegada en Streamlit Cloud desde un dispositivo móvil real (una columna, botones táctiles ≥ 48px).
2. **Prueba en Vivo:** Carga de un clip corto (60 s) grabado con el celular para verificar transcripción y generación de mapa mental en ≤ 60 s.
3. **Consumo de Memoria:** Verificación de estabilidad bajo el umbral de 2.7 GB de RAM en Streamlit Cloud.
4. **Protección de Costos:** Comprobación de que la clave de API de Gemini (`GEMINI_API_KEY`) resida exclusivamente en secrets seguros y cuente con tope de gasto activo.
5. **Comportamiento sin Almacenamiento:** Validación de que el audio cargado durante la sesión del usuario resida únicamente en memoria volátil y sea liberado al concluir la sesión.

---

## 6. Puertas de Calidad (Quality Gates)

| Puerta | Responsable | Criterio de Aprobación | Artefacto / Evidencia |
|---|---|---|---|
| **Puerta 1** | Lead PM | Decisión empírica de hipótesis base (H1 glosario, H2 velocidad Whisper, H3 memoria Streamlit, H6 validez JSON Ollama). | Entradas registradas en `odd/tasks/minuta.md` (Log). |
| **Puerta 2** | Lead PM / QA | Diff revisado contra superficie permitida, pruebas unitarias locales en verde, commits convencionales con coautoría. | Ejecución puntual por componente y commits de unidad. |
| **Puerta 3** | QA (Indep.) | URL pública funcionando, modo demo sin fallos, clip en vivo desde celular, sin audio guardado, sin claves expuestas. | Reporte formal en `docs/qa/despliegue.md`. |
| **Cierre** | QA | `python scripts/verificar.py` exit code 0, checklist de la sección 9 completo y pitch cronometrado ≤ 3:00. | Reporte final y aprobación de entrega. |

---

## 7. Script Automatizado de Verificación (`scripts/verificar.py`)

El script `scripts/verificar.py` actúa como la puerta de control técnica definitiva del repositorio. Termina con código 0 si y solo si:
1. Los 4 módulos clave (`minuta.esquemas`, `app.streamlit_app`, `entrenamiento.generar_sinteticos`, `evaluacion.terminos`) cargan sin error.
2. El archivo `.env` NO está presente en el índice de Git.
3. Ningún archivo con extensión de audio (`*.m4a`, `*.mp3`, `*.wav`, `*.ogg`, `*.webm`, `*.aac`) está en el índice de Git.
4. No existen patrones de credenciales reales ni en el historial (`git log -p`) ni en los archivos del árbol.
5. La suite completa de pruebas (`pytest -q`) finaliza con código de salida 0.
