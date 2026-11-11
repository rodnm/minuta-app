# Estrategia de calidad (QA) de Minuta

- **Proyecto:** Minuta, proyecto final de la Diplomatura de Especialización en Ciencia de Datos de Q-Lab PUCP.
- **Rol responsable:** ingeniero de QA del enjambre de agentes.
- **Referencias:** las hipótesis y sus umbrales están en [docs/resultados.md](../resultados.md); la arquitectura, en [docs/arquitectura.md](../arquitectura.md).

---

## 1. Principios

Cada afirmación sobre funcionalidad, seguridad o rendimiento debe tener detrás un comando, una prueba automatizada o un registro observable.

1. **Privacidad:** ningún audio se versiona en Git ni se guarda en el servidor.
2. **Sin credenciales en el repositorio:** se revisan los archivos y el historial (`git log -p`).
3. **Hipótesis pre-registradas:** H1 a H9 tienen oráculos en `evaluacion/` y umbrales fijados antes de ver los datos.
4. **Primero la prueba:** antes de un cambio de comportamiento se escribe la prueba que falla (RED), luego la implementación (GREEN) y después la limpieza, en unidades de cambio revisables.

---

## 2. Niveles de prueba

```text
                  ▲
                 / \
                /   \     De extremo a extremo (Streamlit AppTest)
               /     \    tests/e2e/
              /-------\
             /         \   Oráculos de hipótesis
            /           \  evaluacion/*.py (H1-H9, desde la consola)
           /-------------\
          /               \ Pruebas unitarias de contrato y componentes
         /_________________\ tests/unit/test_*.py (Pydantic v2, proveedores simulados)
```

### 2.1 Pruebas unitarias
- **Ubicación:** `tests/unit/test_*.py`.
- **Enfoque:** el contrato de datos Pydantic v2 (`minuta/esquemas.py`), la validación de citas literales, la estructuración, los proveedores y las exportaciones.
- **Aislamiento:** no llaman a APIs externas ni descargan modelos pesados. Usan los fixtures de `data/fixtures/` y proveedores simulados.

### 2.2 Oráculos de hipótesis
- **Ubicación:** `evaluacion/*.py` y `tests/unit/test_evaluacion_*.py`.
- **Enfoque:** medir H1 (glosario), H2 (velocidad de Whisper), H4 (detector), H5 (ahorro de tokens), H6 (JSON válido con Ollama), H8 (tareas) y H9 (mapa mental).
- **Determinismo:** la app llama a los LLM con temperatura 0. El generador de sintéticos sin API no es reproducible entre procesos, porque usa `hash(tipo)` en la semilla.

### 2.3 Pruebas de extremo a extremo
- **Ubicación:** `tests/e2e/`.
- **Herramienta:** `streamlit.testing.v1.AppTest`.
- **Alcance:**
  - la app arranca con el modo demo apagado, y el interruptor muestra el ejemplo precalculado;
  - el cambio entre las plantillas *Ponencia / Clase / Charla*, *Reunión* y *Entrevista*;
  - los botones ▶ [mm:ss] y la posición del reproductor;
  - los botones de exportación;
  - sin `GEMINI_API_KEY`, la app muestra un error claro y se detiene.

---

## 3. Seguridad y privacidad

- **Audio:** no se versionan archivos `*.m4a`, `*.mp3`, `*.wav`, `*.ogg`, `*.webm` ni `*.aac`. El audio de evaluación queda en `data/privado/`, que está en `.gitignore`.
- **Índice de Git:** `scripts/verificar.py` falla si encuentra `.env` o archivos de audio en `git ls-files`.
- **Credenciales:** `scripts/verificar.py` busca patrones de claves de API (`AIza…`, `sk-…`, `ghp_…`, llaves privadas e identificadores de claves de AWS) en los archivos del árbol y en el historial (`git log -p`).

---

## 4. Verificación del despliegue (pendiente)

No hay URL pública todavía (H3 pendiente). Cuando exista, se verificará:
1. la app desde un celular real (una columna y botones táctiles);
2. un clip de 60 s grabado con el celular, procesado en ≤ 60 s;
3. el uso de memoria bajo 2.7 GB en Streamlit Community Cloud;
4. que `GEMINI_API_KEY` esté solo en los secrets y con un tope de gasto;
5. que el audio subido no se guarde al terminar la sesión.

---

## 5. Puertas de calidad

| Puerta | Criterio | Evidencia |
|---|---|---|
| **1. Hipótesis base** | H1, H2, H3 y H6 decididas. | [docs/resultados.md](../resultados.md) |
| **2. Cada unidad de cambio** | Diff revisado, pruebas de la unidad en verde y commit propio con coautoría declarada. | Historial de Git. |
| **3. Despliegue** | URL pública verificada según la sección 4. | Pendiente. |
| **Cierre** | `python scripts/verificar.py` termina con código 0, el checklist de la sección 9 está completo y el pitch dura ≤ 3:00. | [checklist_seccion9.md](checklist_seccion9.md) y [docs/pitch.md](../pitch.md) |

---

## 6. `scripts/verificar.py`

Termina con código 0 solo si:
1. los módulos clave (`minuta.esquemas`, `app.streamlit_app`, `entrenamiento.generar_sinteticos` y `evaluacion.terminos`) se importan sin error;
2. `.env` no está en el índice de Git;
3. ningún archivo de audio está en el índice de Git;
4. no hay patrones de credenciales en el historial (`git log -p`) ni en los archivos del árbol;
5. la suite de pruebas (`pytest -q`) termina con código 0.

Para correrlo hacen falta las dependencias de desarrollo: `pip install -r requirements-dev.txt`.
