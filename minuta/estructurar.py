"""Módulo de estructuración Map-Reduce de transcripciones para Minuta.

Convierte transcripciones de audio en resultados estructurados y validados con Pydantic v2
para las tres plantillas del sistema: Ponencia, Reunión y Entrevista.

Aplica estrategia Map-Reduce:
1. Particiona la transcripción en bloques cronológicos de ~10 minutos (<= 600 segundos).
2. Fase Map: extrae ideas, to-do, acuerdos y ramas del mapa mental por bloque.
3. Fase Reduce: agrega y unifica los resultados en el esquema objetivo y construye el MapaMental.
4. Validación estricta: descarta nodos y elementos cuyas citas no sean subcadenas literales.
"""

from __future__ import annotations

import copy
from typing import Any, Literal, Sequence
from pydantic import BaseModel

from minuta.detector import DetectorSegmentos
from minuta.esquemas import (
    Acuerdo,
    CodigoLibro,
    Evidencia,
    FragmentoCodificado,
    MapaMental,
    NodoMapa,
    Pendiente,
    ResultadoEntrevista,
    ResultadoPonencia,
    ResultadoReunion,
    Segmento,
    Tarea,
    Tema,
    Transcripcion,
    localizar_cita_literal,
)
from minuta.proveedores import ProveedorLLM

TipoPlantilla = Literal["ponencia", "reunion", "entrevista"]
ModoEstructuracion = Literal["solo_llm", "detector"]


def particionar_en_bloques(
    segmentos: Sequence[Segmento],
    max_duracion_bloque_s: float = 600.0,
) -> list[list[Segmento]]:
    """Agrupa segmentos cronológicos en bloques de duración acumulada <= max_duracion_bloque_s (~10 min).

    Si la transcripción completa dura menos o igual al umbral, retorna un solo bloque.
    """
    if not segmentos:
        return []

    bloques: list[list[Segmento]] = []
    bloque_actual: list[Segmento] = []
    duracion_acumulada: float = 0.0

    for seg in segmentos:
        dur_seg = max(0.0, seg.fin_s - seg.inicio_s)
        # Si agregar el segmento sobrepasa el límite y el bloque ya tiene segmentos, cerramos bloque
        if bloque_actual and (duracion_acumulada + dur_seg > max_duracion_bloque_s):
            bloques.append(bloque_actual)
            bloque_actual = [seg]
            duracion_acumulada = dur_seg
        else:
            bloque_actual.append(seg)
            duracion_acumulada += dur_seg

    if bloque_actual:
        bloques.append(bloque_actual)

    return bloques


def _comprobar_cita_literal(ev: Evidencia, segmentos: list[Segmento]) -> bool:
    """Verifica si la cita de evidencia es una subcadena literal en los segmentos del bloque.

    Si la encuentra, reescribe segmento_ids con los segmentos donde está la cita e inicio_s con
    el inicio del primero de ellos, para que el botón ▶ salte al lugar real y no al que inventó el LLM.
    """
    if not ev.cita or not ev.cita.strip():
        return False

    # 1. Buscar primero en los segmentos referenciados por el modelo; 2. luego en todo el bloque
    ids_referenciados = {str(x) for x in ev.segmento_ids}
    segs_referenciados = [s for s in segmentos if str(s.id) in ids_referenciados]
    encontrados = localizar_cita_literal(ev.cita, segs_referenciados) if segs_referenciados else []
    if not encontrados:
        encontrados = localizar_cita_literal(ev.cita, segmentos)
    if not encontrados:
        return False

    ev.segmento_ids = [s.id for s in encontrados]
    ev.inicio_s = encontrados[0].inicio_s
    return True


def _filtrar_nodos_recursivo(
    nodos: list[NodoMapa],
    segmentos: list[Segmento],
) -> tuple[list[NodoMapa], int]:
    """Filtra recursivamente los nodos del mapa mental descartando aquellos con citas no literales."""
    nodos_filtrados: list[NodoMapa] = []
    descartados: int = 0

    for nodo in nodos:
        if nodo.evidencia is not None:
            if not _comprobar_cita_literal(nodo.evidencia, segmentos):
                # Cita no literal: descartar el nodo completo y contar
                descartados += 1
                continue

        # Procesar hijos recursivamente
        hijos_filtrados, desc_hijos = _filtrar_nodos_recursivo(nodo.hijos, segmentos)
        descartados += desc_hijos

        nuevo_nodo = NodoMapa(
            id=nodo.id,
            titulo=nodo.titulo,
            resumen=nodo.resumen,
            evidencia=nodo.evidencia,
            hijos=hijos_filtrados,
        )
        nodos_filtrados.append(nuevo_nodo)

    return nodos_filtrados, descartados


def validar_y_descartar_no_literales(
    resultado: ResultadoPonencia | ResultadoReunion | ResultadoEntrevista,
    segmentos: list[Segmento],
) -> tuple[ResultadoPonencia | ResultadoReunion | ResultadoEntrevista, int]:
    """Valida todas las evidencias del resultado contra los segmentos dados.

    Cualquier elemento o nodo cuya cita no sea una subcadena literal es descartado
    y contabilizado en el número de descartados.
    """
    descartados: int = 0

    # 1. Filtrar MapaMental
    raiz_original = resultado.mapa.raiz
    hijos_filtrados, desc_mapa = _filtrar_nodos_recursivo(raiz_original.hijos, segmentos)
    descartados += desc_mapa

    nueva_raiz = NodoMapa(
        id=raiz_original.id,
        titulo=raiz_original.titulo,
        resumen=raiz_original.resumen,
        evidencia=None,  # La raíz nunca lleva evidencia
        hijos=hijos_filtrados,
    )
    nuevo_mapa = MapaMental(titulo=resultado.mapa.titulo, raiz=nueva_raiz)

    # 2. Filtrar elementos específicos de la plantilla
    if isinstance(resultado, ResultadoPonencia):
        ideas_filtradas: list[Tema] = []
        for tema in resultado.ideas_clave:
            evs_validas = [e for e in tema.evidencias if _comprobar_cita_literal(e, segmentos)]
            descartados += len(tema.evidencias) - len(evs_validas)
            if evs_validas:
                ideas_filtradas.append(
                    Tema(titulo=tema.titulo, resumen=tema.resumen, evidencias=evs_validas)
                )

        preguntas_filtradas: list[Pendiente] = []
        for p in resultado.preguntas:
            if _comprobar_cita_literal(p.evidencia, segmentos):
                preguntas_filtradas.append(p)
            else:
                descartados += 1

        resultado_filtrado = ResultadoPonencia(
            resumen_general=resultado.resumen_general,
            ideas_clave=ideas_filtradas,
            preguntas=preguntas_filtradas,
            mapa=nuevo_mapa,
            descartados=resultado.descartados + descartados,
            modo=resultado.modo,
        )
        return resultado_filtrado, descartados

    if isinstance(resultado, ResultadoReunion):
        temas_filtrados: list[Tema] = []
        for tema in resultado.temas:
            evs_validas = [e for e in tema.evidencias if _comprobar_cita_literal(e, segmentos)]
            descartados += len(tema.evidencias) - len(evs_validas)
            if evs_validas:
                temas_filtrados.append(
                    Tema(titulo=tema.titulo, resumen=tema.resumen, evidencias=evs_validas)
                )

        acuerdos_filtrados: list[Acuerdo] = []
        for a in resultado.acuerdos:
            if _comprobar_cita_literal(a.evidencia, segmentos):
                acuerdos_filtrados.append(a)
            else:
                descartados += 1

        tareas_filtradas: list[Tarea] = []
        for t in resultado.tareas:
            if _comprobar_cita_literal(t.evidencia, segmentos):
                tareas_filtradas.append(t)
            else:
                descartados += 1

        pendientes_filtrados: list[Pendiente] = []
        for p in resultado.pendientes:
            if _comprobar_cita_literal(p.evidencia, segmentos):
                pendientes_filtrados.append(p)
            else:
                descartados += 1

        resultado_filtrado = ResultadoReunion(
            resumen_general=resultado.resumen_general,
            temas=temas_filtrados,
            acuerdos=acuerdos_filtrados,
            tareas=tareas_filtradas,
            pendientes=pendientes_filtrados,
            mapa=nuevo_mapa,
            descartados=resultado.descartados + descartados,
            modo=resultado.modo,
        )
        return resultado_filtrado, descartados

    if isinstance(resultado, ResultadoEntrevista):
        fragmentos_filtrados: list[FragmentoCodificado] = []
        for f in resultado.fragmentos:
            if _comprobar_cita_literal(f.evidencia, segmentos):
                fragmentos_filtrados.append(f)
            else:
                descartados += 1

        resultado_filtrado = ResultadoEntrevista(
            libro=resultado.libro,
            fragmentos=fragmentos_filtrados,
            resumen_por_codigo=resultado.resumen_por_codigo,
            mapa=nuevo_mapa,
            descartados=resultado.descartados + descartados,
            modo=resultado.modo,
        )
        return resultado_filtrado, descartados

    return resultado, 0


def _generar_prompt_map(
    segmentos: list[Segmento],
    tipo_plantilla: TipoPlantilla,
    bloque_idx: int = 1,
    total_bloques: int = 1,
    candidatos_todo: list[Segmento] | None = None,
) -> str:
    """Construye el prompt para la fase Map del procesamiento estructurado."""
    texto_segmentos = "\n".join(
        f"[{s.id}] ({s.inicio_s:.1f}s - {s.fin_s:.1f}s): {s.texto}" for s in segmentos
    )

    instrucciones_plantilla = {
        "ponencia": (
            "Extrae un resumen_general conciso, las ideas_clave principales (cada una con sus evidencias),\n"
            "preguntas abiertas o temas no resueltos, y un mapa mental estructurado en árbol."
        ),
        "reunion": (
            "Extrae un resumen_general de la reunión, temas discutidos, acuerdos pactados,\n"
            "tareas asignadas (to-do lists con responsable y fecha si se mencionan), pendientes y mapa mental."
        ),
        "entrevista": (
            "Extrae el libro de códigos temáticos, fragmentos codificados con evidencia textual estricta,\n"
            "resumen por cada código temático, y un mapa mental estructurado."
        ),
    }[tipo_plantilla]

    seccion_candidatos = ""
    if candidatos_todo and tipo_plantilla == "reunion":
        seccion_candidatos = (
            "\nSEGMENTOS CANDIDATOS A TAREAS O ACUERDOS DETECTADOS PREVIAMENTE:\n"
            + "\n".join(f"- [{s.id}] ({s.inicio_s:.1f}s): {s.texto}" for s in candidatos_todo)
            + "\n"
        )

    return f"""Eres el sistema NLP de estructuración de audio de Minuta.
Analiza la siguiente transcripción correspondiente al Bloque {bloque_idx} de {total_bloques}.

INSTRUCCIONES CLAVE:
1. {instrucciones_plantilla}
2. REGLA ESTRICTA DE EVIDENCIA: Todas las citas en Evidencia (campo 'cita') DEBEN ser subcadenas literales y exactas
   del texto transcrito en los segmentos. No parafrasees las citas bajo ninguna circunstancia.
3. MAPA MENTAL:
   - El árbol debe tener entre 2 y 4 niveles de profundidad y entre 4 y 8 ramas principales.
   - El nodo raíz no lleva evidencia ('evidencia': null).
   - Todos los nodos hijos y hojas DEBEN llevar 'evidencia' con su respectiva cita literal exacta y tiempo de inicio.
{seccion_candidatos}
TRANSCRIPCIÓN DEL BLOQUE:
{texto_segmentos}
"""


def _prefijar_ids(nodo: NodoMapa, prefijo: str) -> NodoMapa:
    """Copia el subárbol anteponiendo el prefijo a cada id, para que no choquen entre bloques."""
    return nodo.model_copy(
        update={
            "id": f"{prefijo}{nodo.id}",
            "hijos": [_prefijar_ids(hijo, prefijo) for hijo in nodo.hijos],
        }
    )


def _seleccionar_ramas_por_cupo(
    ramas_por_bloque: list[list[NodoMapa]],
    max_ramas: int,
) -> list[NodoMapa]:
    """Reparte las max_ramas ramas principales entre los bloques para cubrir todo el audio.

    Toma por turnos la siguiente rama de cada bloque, sin repetir títulos. Si hay más bloques
    con ramas que cupos, elige bloques espaciados a lo largo del audio. El resultado conserva
    el orden cronológico (bloque y posición dentro del bloque).
    """
    bloques = [i for i, ramas in enumerate(ramas_por_bloque) if ramas]
    if max_ramas <= 0 or not bloques:
        return []
    if len(bloques) > max_ramas:
        paso = (len(bloques) - 1) / (max_ramas - 1) if max_ramas > 1 else 0.0
        bloques = [bloques[round(k * paso)] for k in range(max_ramas)]

    siguiente = {i: 0 for i in bloques}
    titulos_vistos: set[str] = set()
    elegidas: list[tuple[int, int, NodoMapa]] = []

    while len(elegidas) < max_ramas:
        hubo_avance = False
        for i in bloques:
            if len(elegidas) >= max_ramas:
                break
            ramas = ramas_por_bloque[i]
            while siguiente[i] < len(ramas):
                pos = siguiente[i]
                siguiente[i] += 1
                clave = ramas[pos].titulo.strip().lower()
                if clave not in titulos_vistos:
                    titulos_vistos.add(clave)
                    elegidas.append((i, pos, ramas[pos]))
                    hubo_avance = True
                    break
        if not hubo_avance:
            break

    elegidas.sort(key=lambda e: (e[0], e[1]))
    return [rama for _, _, rama in elegidas]


def _unificar_mapas(
    mapas: list[MapaMental],
    titulo_general: str,
    max_ramas: int = 8,
) -> MapaMental:
    """Unifica las ramas principales de múltiples árboles de mapa mental bajo una raíz común.

    Los ids de cada bloque i se renumeran como b{i}-{id} y las ramas se eligen con un cupo
    por bloque, para que el mapa no pierda el final del audio.
    """
    ramas_por_bloque = [
        [_prefijar_ids(hijo, f"b{i}-") for hijo in m.raiz.hijos]
        for i, m in enumerate(mapas, start=1)
    ]
    todas_las_ramas = _seleccionar_ramas_por_cupo(ramas_por_bloque, max_ramas)

    raiz_unificada = NodoMapa(
        id="root",
        titulo=titulo_general,
        resumen=None,
        evidencia=None,
        hijos=todas_las_ramas,
    )
    return MapaMental(titulo=titulo_general, raiz=raiz_unificada)


def estructurar_transcripcion(
    transcripcion: Transcripcion,
    tipo_plantilla: TipoPlantilla,
    proveedor: ProveedorLLM,
    modo: ModoEstructuracion = "solo_llm",
    detector: DetectorSegmentos | None = None,
) -> ResultadoPonencia | ResultadoReunion | ResultadoEntrevista:
    """Estructura una transcripción aplicando estrategia Map-Reduce por bloques de ~10 minutos.

    Parámetros:
    - transcripcion: Objeto Transcripcion validado con segmentos temporales.
    - tipo_plantilla: "ponencia" (defecto), "reunion" o "entrevista".
    - proveedor: Instancia de ProveedorLLM (Gemini, Ollama o Mock).
    - modo: "solo_llm" o "detector".
    - detector: Instancia opcional de DetectorSegmentos. Si modo="detector" y no se pasa uno,
      se intenta instanciar; si el modelo no está disponible, cae suavemente a "solo_llm".

    Retorna:
    - ResultadoPonencia, ResultadoReunion o ResultadoEntrevista con evidencias literales estrictas.
    """
    esquema_cls: type[ResultadoPonencia | ResultadoReunion | ResultadoEntrevista]
    if tipo_plantilla == "ponencia":
        esquema_cls = ResultadoPonencia
    elif tipo_plantilla == "reunion":
        esquema_cls = ResultadoReunion
    elif tipo_plantilla == "entrevista":
        esquema_cls = ResultadoEntrevista
    else:
        raise ValueError(f"Tipo de plantilla no soportada: '{tipo_plantilla}'")

    modo_efectivo: ModoEstructuracion = modo
    segmentos_activos = list(transcripcion.segmentos)
    candidatos_todo: list[Segmento] = []

    # Integración con el detector de segmentos (filtrado de relleno y extracción de to-do)
    if modo == "detector":
        if detector is not None and not detector.disponible:
            # Detector provisto explícitamente pero no disponible: fallback a solo_llm
            modo_efectivo = "solo_llm"
            segmentos_activos = list(transcripcion.segmentos)
            candidatos_todo = []
        elif detector is not None and detector.disponible:
            # Detector provisto y disponible: procesar y filtrar
            proc = detector.procesar_transcripcion(transcripcion, tipo_plantilla=tipo_plantilla)
            segmentos_activos = proc["segmentos_procesados"]
            candidatos_todo = proc.get("candidatos_todo", [])
            modo_efectivo = "detector"
            if not segmentos_activos and transcripcion.segmentos:
                segmentos_activos = list(transcripcion.segmentos)
        else:
            # detector is None: intentar instanciar DetectorSegmentos()
            det_default = DetectorSegmentos()
            if det_default.disponible:
                proc = det_default.procesar_transcripcion(transcripcion, tipo_plantilla=tipo_plantilla)
                segmentos_activos = proc["segmentos_procesados"]
                candidatos_todo = proc.get("candidatos_todo", [])
                modo_efectivo = "detector"
            else:
                # Si no se pasó detector y el entorno no tiene mmBERT instalado,
                # mantener modo="detector" sin filtrado de segmentos para compatibilidad de contrato
                modo_efectivo = "detector"
                segmentos_activos = list(transcripcion.segmentos)
                candidatos_todo = []

    if not segmentos_activos:
        # Caso borde: transcripción vacía
        mapa_vacio = MapaMental(titulo="Sin contenido", raiz=NodoMapa(id="root", titulo="Sin contenido"))
        if tipo_plantilla == "ponencia":
            return ResultadoPonencia(
                resumen_general="", ideas_clave=[], preguntas=[], mapa=mapa_vacio, modo=modo_efectivo
            )
        if tipo_plantilla == "reunion":
            return ResultadoReunion(
                resumen_general="", temas=[], acuerdos=[], tareas=[], pendientes=[], mapa=mapa_vacio, modo=modo_efectivo
            )
        return ResultadoEntrevista(
            libro=[], fragmentos=[], resumen_por_codigo={}, mapa=mapa_vacio, modo=modo_efectivo
        )

    # Particionar en bloques de ~10 minutos (<= 600 segundos) sobre los segmentos filtrados
    duracion_activa = sum(max(0.0, s.fin_s - s.inicio_s) for s in segmentos_activos)
    if duracion_activa <= 600.0:
        bloques = [list(segmentos_activos)]
    else:
        bloques = particionar_en_bloques(segmentos_activos, max_duracion_bloque_s=600.0)

    # Fase MAP: Procesar cada bloque individualmente
    resultados_bloques: list[ResultadoPonencia | ResultadoReunion | ResultadoEntrevista] = []

    for idx, bloque_segs in enumerate(bloques, start=1):
        cands_bloque = [c for c in candidatos_todo if any(s.id == c.id for s in bloque_segs)]
        prompt = _generar_prompt_map(
            bloque_segs,
            tipo_plantilla=tipo_plantilla,
            bloque_idx=idx,
            total_bloques=len(bloques),
            candidatos_todo=cands_bloque,
        )
        res_bloque = proveedor.generar_estructurado(prompt, esquema_cls)

        # Validación y descarte de citas no literales del bloque
        res_filtrado, desc = validar_y_descartar_no_literales(res_bloque, bloque_segs)
        resultados_bloques.append(res_filtrado)

    # Si solo hay un bloque, no se requiere fase Reduce compleja
    if len(resultados_bloques) == 1:
        res_unico = resultados_bloques[0]
        res_unico.modo = modo_efectivo
        return res_unico

    # Fase REDUCE: Unificar resultados parciales de múltiples bloques
    total_descartados = sum(r.descartados for r in resultados_bloques)

    def _unificar_resumenes() -> str:
        # Solo Ponencia y Reunión tienen resumen_general; Entrevista no lo tiene.
        return "\n\n".join(
            f"[Bloque {i}] {r.resumen_general}"
            for i, r in enumerate(resultados_bloques, start=1)
            if r.resumen_general.strip()
        )

    titulo_mapa = resultados_bloques[0].mapa.titulo or transcripcion.audio_id
    mapas = [r.mapa for r in resultados_bloques]
    mapa_unificado = _unificar_mapas(mapas, titulo_general=titulo_mapa)

    if tipo_plantilla == "ponencia":
        todas_ideas: list[Tema] = []
        ideas_vistas: set[str] = set()
        for r in resultados_bloques:
            assert isinstance(r, ResultadoPonencia)
            for idea in r.ideas_clave:
                k = idea.titulo.strip().lower()
                if k not in ideas_vistas:
                    ideas_vistas.add(k)
                    todas_ideas.append(idea)

        todas_preguntas: list[Pendiente] = []
        for r in resultados_bloques:
            assert isinstance(r, ResultadoPonencia)
            todas_preguntas.extend(r.preguntas)

        return ResultadoPonencia(
            resumen_general=_unificar_resumenes(),
            ideas_clave=todas_ideas,
            preguntas=todas_preguntas,
            mapa=mapa_unificado,
            descartados=total_descartados,
            modo=modo_efectivo,
        )

    if tipo_plantilla == "reunion":
        todos_temas: list[Tema] = []
        temas_vistos: set[str] = set()
        for r in resultados_bloques:
            assert isinstance(r, ResultadoReunion)
            for tema in r.temas:
                k = tema.titulo.strip().lower()
                if k not in temas_vistos:
                    temas_vistos.add(k)
                    todos_temas.append(tema)

        todos_acuerdos: list[Acuerdo] = []
        todas_tareas: list[Tarea] = []
        todos_pendientes: list[Pendiente] = []

        for r in resultados_bloques:
            assert isinstance(r, ResultadoReunion)
            todos_acuerdos.extend(r.acuerdos)
            todas_tareas.extend(r.tareas)
            todos_pendientes.extend(r.pendientes)

        return ResultadoReunion(
            resumen_general=_unificar_resumenes(),
            temas=todos_temas,
            acuerdos=todos_acuerdos,
            tareas=todas_tareas,
            pendientes=todos_pendientes,
            mapa=mapa_unificado,
            descartados=total_descartados,
            modo=modo_efectivo,
        )

    # Entrevista
    todos_libros: list[CodigoLibro] = []
    codigos_vistos: set[str] = set()
    todos_fragmentos: list[FragmentoCodificado] = []
    resumen_codigos: dict[str, str] = {}

    for r in resultados_bloques:
        assert isinstance(r, ResultadoEntrevista)
        for lib in r.libro:
            if lib.codigo not in codigos_vistos:
                codigos_vistos.add(lib.codigo)
                todos_libros.append(lib)
        todos_fragmentos.extend(r.fragmentos)
        for cod, res_txt in r.resumen_por_codigo.items():
            if cod in resumen_codigos:
                resumen_codigos[cod] = f"{resumen_codigos[cod]} {res_txt}".strip()
            else:
                resumen_codigos[cod] = res_txt

    return ResultadoEntrevista(
        libro=todos_libros,
        fragmentos=todos_fragmentos,
        resumen_por_codigo=resumen_codigos,
        mapa=mapa_unificado,
        descartados=total_descartados,
        modo=modo_efectivo,
    )
