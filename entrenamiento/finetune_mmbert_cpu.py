"""Módulo de fine-tuning y entrenamiento en CPU de mmBERT-small para Minuta.

Entrena un clasificador de 5 clases para detección de intención en segmentos de transcripción:
- idea
- tarea
- acuerdo
- pregunta
- relleno

Soporta ejecución en CPU con prueba rápida (--prueba-rapida con 50 ejemplos)
y cálculo de pesos de clase para mitigar el desbalance de clases minoritarias (tarea y acuerdo).
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# Constantes del clasificador
# ---------------------------------------------------------------------------

CLASES_ESTANDAR: list[str] = ["idea", "tarea", "acuerdo", "pregunta", "relleno"]
LABEL2ID: dict[str, int] = {c: i for i, c in enumerate(CLASES_ESTANDAR)}
ID2LABEL: dict[int, str] = {i: c for i, c in enumerate(CLASES_ESTANDAR)}

MODELO_BASE_DEFAULT: str = "jhu-clsp/mmBERT-small"
SALIDA_MODELO_DEFAULT: str = "modelos/minuta-detector-mmbert-small"
RUTA_DATOS_DEFAULT: str = "entrenamiento/datos/sinteticos_entrenamiento.json"

# Verificación defensiva de dependencias pesadas de ML
try:
    import torch
    import torch.nn as nn
    import transformers
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )
    _TORCH_DISPONIBLE: bool = True
except ImportError:
    _TORCH_DISPONIBLE = False


# ---------------------------------------------------------------------------
# 1. Carga y Procesamiento de Datos
# ---------------------------------------------------------------------------

def cargar_dataset_sintetico(ruta_json: str | Path) -> list[dict[str, str]]:
    """Carga segmentos transcritos desde un archivo JSON sintético.

    Soporta formatos estructurados con 'conversaciones' o listas planas de segmentos.
    Filtra entradas con texto vacío o etiquetas que no pertenezcan a CLASES_ESTANDAR.
    """
    p = Path(ruta_json)
    if not p.exists():
        raise FileNotFoundError(f"No se encontró el archivo de datos sintéticos: {p.resolve()}")

    contenido = json.loads(p.read_text(encoding="utf-8"))
    ejemplos_crudos: list[dict[str, Any]] = []

    if isinstance(contenido, dict):
        if "conversaciones" in contenido and isinstance(contenido["conversaciones"], list):
            for conv in contenido["conversaciones"]:
                for seg in conv.get("segmentos", []):
                    ejemplos_crudos.append(seg)
        elif "segmentos" in contenido and isinstance(contenido["segmentos"], list):
            ejemplos_crudos = contenido["segmentos"]
    elif isinstance(contenido, list):
        ejemplos_crudos = contenido

    ejemplos_filtrados: list[dict[str, str]] = []
    for item in ejemplos_crudos:
        texto = item.get("texto", "")
        etiqueta = item.get("etiqueta", "")

        if not isinstance(texto, str) or not texto.strip():
            continue
        if etiqueta not in CLASES_ESTANDAR:
            continue

        ejemplos_filtrados.append({
            "texto": texto.strip(),
            "etiqueta": etiqueta,
        })

    return ejemplos_filtrados


def dividir_dataset_por_conversacion(
    datos: str | Path | dict[str, Any],
    prop_train: float = 0.70,
    prop_val: float = 0.15,
    prop_test: float = 0.15,
    semilla: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    """Divide un dataset sintético estructurado en train, val y test agrupando POR CONVERSACIÓN.

    Garantiza que ningún segmento de una misma conversación quede repartido entre
    distintas particiones (prevención de fuga de datos / data leakage) y estratifica
    la selección según el tipo de conversación ('ponencia', 'reunion', 'entrevista').

    Retorna:
        (train_items, val_items, test_items, info_particion)
    """
    if isinstance(datos, (str, Path)):
        p = Path(datos)
        if not p.exists():
            raise FileNotFoundError(f"No se encontró el archivo de datos: {p.resolve()}")
        contenido = json.loads(p.read_text(encoding="utf-8"))
    elif isinstance(datos, dict):
        contenido = datos
    else:
        raise ValueError("El parámetro 'datos' debe ser una ruta a archivo JSON o un diccionario.")

    conversaciones = contenido.get("conversaciones", [])
    if not conversaciones:
        # Fallback para listas planas sin estructura de conversaciones
        ejemplos_planos = cargar_dataset_sintetico(datos) if isinstance(datos, (str, Path)) else []
        rng = random.Random(semilla)
        rng.shuffle(ejemplos_planos)
        c1 = int(len(ejemplos_planos) * prop_train)
        c2 = int(len(ejemplos_planos) * (prop_train + prop_val))
        return ejemplos_planos[:c1], ejemplos_planos[c1:c2], ejemplos_planos[c2:], {}

    # Agrupar conversaciones por tipo (ponencia, reunion, entrevista)
    por_tipo: dict[str, list[dict[str, Any]]] = {}
    for conv in conversaciones:
        t = str(conv.get("tipo", "general"))
        por_tipo.setdefault(t, []).append(conv)

    convs_train: list[dict[str, Any]] = []
    convs_val: list[dict[str, Any]] = []
    convs_test: list[dict[str, Any]] = []

    rng = random.Random(semilla)

    for tipo, lista_conv in sorted(por_tipo.items()):
        # Orden determinista por ID antes de barajar
        lista_ordenada = sorted(lista_conv, key=lambda c: str(c.get("id", "")))
        rng.shuffle(lista_ordenada)

        n = len(lista_ordenada)
        if n == 1:
            convs_train.extend(lista_ordenada)
        elif n == 2:
            convs_train.append(lista_ordenada[0])
            convs_val.append(lista_ordenada[1])
        else:
            # Estratificación asegurando al menos 1 conversación en cada partición si n >= 3
            n_train = max(1, int(round(n * prop_train)))
            if n - n_train < 2 and n >= 3:
                n_train = n - 2
                n_val = 1
                n_test = 1
            else:
                n_val = max(1, int(round(n * prop_val)))
                if n_train + n_val >= n:
                    n_val = max(1, n - n_train - 1)
                n_test = n - n_train - n_val

            convs_train.extend(lista_ordenada[:n_train])
            convs_val.extend(lista_ordenada[n_train : n_train + n_val])
            convs_test.extend(lista_ordenada[n_train + n_val :])

    def extraer_segmentos(conv_list: list[dict[str, Any]]) -> list[dict[str, str]]:
        segmentos: list[dict[str, str]] = []
        for conv in conv_list:
            c_id = str(conv.get("id", ""))
            c_tipo = str(conv.get("tipo", ""))
            for seg in conv.get("segmentos", []):
                texto = seg.get("texto", "")
                etiqueta = seg.get("etiqueta", "")
                if not isinstance(texto, str) or not texto.strip():
                    continue
                if etiqueta not in CLASES_ESTANDAR:
                    continue
                segmentos.append({
                    "texto": texto.strip(),
                    "etiqueta": etiqueta,
                    "conv_id": c_id,
                    "conv_tipo": c_tipo,
                })
        return segmentos

    train_items = extraer_segmentos(convs_train)
    val_items = extraer_segmentos(convs_val)
    test_items = extraer_segmentos(convs_test)

    info_particion = {
        "conv_ids_train": [str(c.get("id", "")) for c in convs_train],
        "conv_ids_val": [str(c.get("id", "")) for c in convs_val],
        "conv_ids_test": [str(c.get("id", "")) for c in convs_test],
        "tipos_en_train": sorted(list({str(c.get("tipo", "")) for c in convs_train})),
        "tipos_en_val": sorted(list({str(c.get("tipo", "")) for c in convs_val})),
        "tipos_en_test": sorted(list({str(c.get("tipo", "")) for c in convs_test})),
        "conteo_convs": {
            "train": len(convs_train),
            "val": len(convs_val),
            "test": len(convs_test),
            "total": len(convs_train) + len(convs_val) + len(convs_test),
        },
        "conteo_segmentos": {
            "train": len(train_items),
            "val": len(val_items),
            "test": len(test_items),
            "total": len(train_items) + len(val_items) + len(test_items),
        },
    }

    return train_items, val_items, test_items, info_particion


def calcular_metricas_clasificacion(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    clases: Sequence[str] = CLASES_ESTANDAR,
) -> dict[str, Any]:
    """Calcula métricas estándar de clasificación multi-clase (precisión, recall, F1, matriz de confusión)."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true e y_pred deben tener la misma longitud.")

    n = len(y_true)
    if n == 0:
        return {
            "exactitud": 0.0,
            "f1_macro": 0.0,
            "por_clase": {},
            "matriz_confusion": [],
        }

    correctos = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    exactitud = round(correctos / n, 4)

    por_clase: dict[str, dict[str, float | int]] = {}
    f1_list: list[float] = []

    for c in clases:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        soporte = tp + fn

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        por_clase[c] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "soporte": soporte,
        }
        f1_list.append(f1)

    f1_macro = round(sum(f1_list) / len(f1_list), 4) if f1_list else 0.0

    # Matriz de confusión (filas: true, columnas: pred)
    c2idx = {c: i for i, c in enumerate(clases)}
    matriz = [[0 for _ in range(len(clases))] for _ in range(len(clases))]
    for t, p in zip(y_true, y_pred):
        if t in c2idx and p in c2idx:
            matriz[c2idx[t]][c2idx[p]] += 1

    return {
        "exactitud": exactitud,
        "f1_macro": f1_macro,
        "por_clase": por_clase,
        "matriz_confusion": matriz,
        "clases": list(clases),
    }


def calcular_pesos_clase(
    etiquetas: Sequence[str],
    metodo: str = "balanceado",
) -> dict[str, float]:
    """Calcula pesos de clase inversamente proporcionales a las frecuencias observadas.

    Aplica la fórmula estándar de balanceo:
        w_c = N / (C * n_c)
    donde N es el total de ejemplos, C el número de clases presentes y n_c el conteo de la clase c.
    Garantiza que las clases minoritarias (ej. tarea o acuerdo) reciban mayor peso relativo.
    """
    if not etiquetas:
        return {}

    conteos = Counter(e for e in etiquetas if e in CLASES_ESTANDAR)
    if not conteos:
        return {}

    total_muestras = sum(conteos.values())
    total_clases = len(conteos)

    pesos: dict[str, float] = {}
    for c, n in conteos.items():
        w = total_muestras / (total_clases * n)
        pesos[c] = round(float(w), 4)

    return pesos


# ---------------------------------------------------------------------------
# 2. Utilidades para PyTorch / HuggingFace (si están disponibles)
# ---------------------------------------------------------------------------

if _TORCH_DISPONIBLE:
    class WeightedTrainer(Trainer):
        """Subclase de Trainer que aplica CrossEntropyLoss ponderada con pesos de clase."""

        def __init__(self, *args, class_weights: torch.Tensor | None = None, **kwargs):
            super().__init__(*args, **kwargs)
            self.class_weights = class_weights

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.get("labels")
            outputs = model(**inputs)
            logits = outputs.get("logits")

            if self.class_weights is not None:
                weights = self.class_weights.to(logits.device)
                loss_fct = nn.CrossEntropyLoss(weight=weights)
            else:
                loss_fct = nn.CrossEntropyLoss()

            loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
            return (loss, outputs) if return_outputs else loss


# ---------------------------------------------------------------------------
# 3. Función Principal de Entrenamiento en CPU
# ---------------------------------------------------------------------------

def imprimir_reporte_metricas(metricas: dict[str, Any], titulo: str = "MÉTRICAS DE EVALUACIÓN") -> None:
    """Imprime en consola el reporte formateado de clasificación multi-clase."""
    print("\n" + "=" * 70)
    print(f" {titulo}")
    print("=" * 70)
    print(f" Exactitud global: {metricas.get('exactitud', 0.0) * 100:.2f} %")
    print(f" F1 Macro:         {metricas.get('f1_macro', 0.0):.4f}")
    print("-" * 70)
    print(f" {'Clase':<12} | {'Precisión':<10} | {'Recall':<10} | {'F1-score':<10} | {'Soporte':<8}")
    print("-" * 70)
    por_clase = metricas.get("por_clase", {})
    for c in CLASES_ESTANDAR:
        val = por_clase.get(c, {})
        p = val.get("precision", 0.0)
        r = val.get("recall", 0.0)
        f1 = val.get("f1_score", 0.0)
        sup = val.get("soporte", 0)
        print(f" {c:<12} | {p:<10.4f} | {r:<10.4f} | {f1:<10.4f} | {sup:<8}")
    print("-" * 70)
    print(" Matriz de confusión (Filas: Real, Columnas: Predicción):")
    header_mat = "       " + " ".join(f"{c[:4]:>6}" for c in CLASES_ESTANDAR)
    print(header_mat)
    matriz = metricas.get("matriz_confusion", [])
    for i, fila in enumerate(matriz):
        nom = CLASES_ESTANDAR[i]
        fila_str = " ".join(f"{v:>6}" for v in fila)
        print(f" {nom[:6]:<6} {fila_str}")
    print("=" * 70 + "\n")


def demostrar_clasificacion_segmentos(
    modelo_dir: str | Path,
    ruta_transcripcion: str | Path,
    etiqueta_fuente: str = "Transcripción",
) -> dict[str, Any]:
    """Carga el modelo afinado y clasifica los segmentos de una transcripción.

    Cuenta los segmentos clasificados en cada categoría y cuántos se filtran como relleno.
    """
    p = Path(ruta_transcripcion)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo de transcripción: {p}")

    contenido = json.loads(p.read_text(encoding="utf-8"))
    segmentos = []
    if isinstance(contenido, dict):
        if "segmentos" in contenido and isinstance(contenido["segmentos"], list):
            segmentos = contenido["segmentos"]
    elif isinstance(contenido, list):
        segmentos = contenido

    if not segmentos:
        print(f"[AVISO] No se encontraron segmentos en {p}")
        return {}

    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(modelo_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(modelo_dir))
    model.eval()

    device = next(model.parameters()).device
    textos = [s.get("texto", "") for s in segmentos]
    predicciones: list[str] = []

    batch_size = 16
    with torch.no_grad():
        for i in range(0, len(textos), batch_size):
            lote = textos[i : i + batch_size]
            enc = tokenizer(lote, truncation=True, max_length=128, padding=True, return_tensors="pt").to(device)
            logits = model(**enc).logits
            preds_ids = torch.argmax(logits, dim=1).cpu().tolist()
            predicciones.extend([ID2LABEL[idx] for idx in preds_ids])

    conteo = Counter(predicciones)
    total = len(predicciones)
    filtrados_relleno = conteo.get("relleno", 0)
    pct_filtrado = (filtrados_relleno / total * 100) if total > 0 else 0.0

    print("\n" + "=" * 60)
    print(f" DEMOSTRACIÓN DE CLASIFICACIÓN ({etiqueta_fuente})")
    print(f" Archivo: {p.name} | Total segmentos: {total}")
    print("-" * 60)
    for c in CLASES_ESTANDAR:
        cnt = conteo.get(c, 0)
        pct = (cnt / total * 100) if total > 0 else 0.0
        print(f" - {c:<10}: {cnt:>3} segmentos ({pct:5.1f} %)")
    print("-" * 60)
    print(f" Segmentos filtrados como 'relleno': {filtrados_relleno} ({pct_filtrado:.1f} %)")
    print("=" * 60 + "\n")

    return {
        "archivo": str(p),
        "total_segmentos": total,
        "conteo_por_clase": dict(conteo),
        "filtrados_relleno": filtrados_relleno,
        "porcentaje_filtrado": round(pct_filtrado, 2),
    }


def entrenar_cpu(
    datos: str | Path = RUTA_DATOS_DEFAULT,
    salida_dir: str | Path = SALIDA_MODELO_DEFAULT,
    modelo_base: str = MODELO_BASE_DEFAULT,
    prueba_rapida: bool = False,
    epochs: int = 3,
    batch_size: int = 8,
    lr: float = 3e-5,
    semilla: int = 42,
    max_length: int = 128,
    evaluar_test: bool = True,
    salida_metricas: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta el pipeline de fine-tuning en CPU para mmBERT-small.

    Particiona el dataset por conversación (70% train, 15% val, 15% test retenido),
    mitiga el desbalance con WeightedTrainer y evalúa métricas completas en test.
    """
    if not _TORCH_DISPONIBLE:
        raise RuntimeError(
            "PyTorch o Transformers no están instalados en este entorno. "
            "Para ejecutar el entrenamiento instale: "
            "pip install torch transformers datasets scikit-learn accelerate"
        )

    # Fijar semillas deterministas
    random.seed(semilla)
    torch.manual_seed(semilla)

    print(f"[INFO] Cargando y particionando dataset sintético desde: {datos}")
    train_items, val_items, test_items, info_part = dividir_dataset_por_conversacion(
        datos,
        prop_train=0.70,
        prop_val=0.15,
        prop_test=0.15,
        semilla=semilla,
    )
    if not train_items:
        raise ValueError(f"No se encontraron ejemplos válidos de entrenamiento en {datos}")

    if prueba_rapida:
        print("[INFO] Modo --prueba-rapida activo: limitando a 50 ejemplos train y 20 eval/test.")
        random.shuffle(train_items)
        train_items = train_items[:50]
        val_items = val_items[:20] if len(val_items) > 20 else val_items
        test_items = test_items[:20] if len(test_items) > 20 else test_items
        epochs = min(epochs, 1)
        batch_size = min(batch_size, 4)

    # Distribución y pesos de clase calculados sobre train_items (sin fuga de val/test)
    etiquetas_train = [ex["etiqueta"] for ex in train_items]
    pesos_dict = calcular_pesos_clase(etiquetas_train)
    print(f"[INFO] Distribución de clases en train: {dict(Counter(etiquetas_train))}")
    print(f"[INFO] Pesos calculados por clase: {pesos_dict}")

    tensor_pesos = torch.tensor(
        [pesos_dict.get(CLASES_ESTANDAR[i], 1.0) for i in range(len(CLASES_ESTANDAR))],
        dtype=torch.float,
    )

    # Carga de Tokenizer y Modelo Base
    print(f"[INFO] Cargando tokenizer y modelo base: {modelo_base}")
    tokenizer = AutoTokenizer.from_pretrained(modelo_base)
    model = AutoModelForSequenceClassification.from_pretrained(
        modelo_base,
        num_labels=len(CLASES_ESTANDAR),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    # Preparación de Dataset PyTorch
    class DatasetTexto(torch.utils.data.Dataset):
        def __init__(self, items, tok, max_len):
            self.items = items
            self.tok = tok
            self.max_len = max_len

        def __len__(self):
            return len(self.items)

        def __getitem__(self, idx):
            item = self.items[idx]
            enc = self.tok(
                item["texto"],
                truncation=True,
                max_length=self.max_len,
                padding="max_length",
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].squeeze(0)
            attention_mask = enc["attention_mask"].squeeze(0)
            label = torch.tensor(LABEL2ID[item["etiqueta"]], dtype=torch.long)
            return {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": label,
            }

    ds_train = DatasetTexto(train_items, tokenizer, max_length)
    ds_eval = DatasetTexto(val_items, tokenizer, max_length)

    salida_path = Path(salida_dir)
    salida_path.mkdir(parents=True, exist_ok=True)

    args_entrenamiento = TrainingArguments(
        output_dir=str(salida_path / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        logging_steps=10,
        save_strategy="no",
        eval_strategy="no",
        use_cpu=True,
        report_to="none",
    )

    trainer = WeightedTrainer(
        model=model,
        args=args_entrenamiento,
        train_dataset=ds_train,
        eval_dataset=ds_eval,
        class_weights=tensor_pesos,
    )

    print(f"[INFO] Iniciando entrenamiento en CPU ({len(train_items)} train, {len(val_items)} val, {epochs} epochs)...")
    trainer.train()

    print(f"[INFO] Guardando modelo y tokenizer en: {salida_path}")
    model.save_pretrained(str(salida_path))
    tokenizer.save_pretrained(str(salida_path))

    # Evaluación en la prueba sintética retenida
    metricas_test: dict[str, Any] = {}
    if evaluar_test and test_items:
        print(f"[INFO] Evaluando en la partición sintética retenida ({len(test_items)} ejemplos)...")
        model.eval()
        device = next(model.parameters()).device
        y_true = [it["etiqueta"] for it in test_items]
        y_pred = []

        batch_eval_size = 16
        with torch.no_grad():
            for i in range(0, len(test_items), batch_eval_size):
                lote = test_items[i : i + batch_eval_size]
                textos = [it["texto"] for it in lote]
                enc = tokenizer(
                    textos,
                    truncation=True,
                    max_length=max_length,
                    padding=True,
                    return_tensors="pt",
                ).to(device)
                logits = model(**enc).logits
                preds_ids = torch.argmax(logits, dim=1).cpu().tolist()
                y_pred.extend([ID2LABEL[idx] for idx in preds_ids])

        metricas_test = calcular_metricas_clasificacion(y_true, y_pred, clases=CLASES_ESTANDAR)
        imprimir_reporte_metricas(metricas_test, titulo="VALIDACIÓN INTERNA SOBRE PRUEBA SINTÉTICA RETENIDA")

    resultado_final = {
        "train_ejemplos": len(train_items),
        "val_ejemplos": len(val_items),
        "test_ejemplos": len(test_items),
        "pesos_clase": pesos_dict,
        "salida_dir": str(salida_path),
        "info_particion": info_part,
        "metricas_test": metricas_test,
        "status": "completado",
    }

    if salida_metricas:
        p_sal = Path(salida_metricas)
        p_sal.parent.mkdir(parents=True, exist_ok=True)
        p_sal.write_text(json.dumps(resultado_final, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[INFO] Métricas guardadas en: {p_sal}")

    return resultado_final


# ---------------------------------------------------------------------------
# 4. CLI Parser
# ---------------------------------------------------------------------------

def construir_parser_cli() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Fine-tuning en CPU de mmBERT-small para el detector de Minuta (5 clases)."
    )
    parser.add_argument(
        "--datos",
        type=str,
        default=RUTA_DATOS_DEFAULT,
        help=f"Ruta al archivo JSON de datos sintéticos (defecto: {RUTA_DATOS_DEFAULT})",
    )
    parser.add_argument(
        "--salida-modelo",
        type=str,
        default=SALIDA_MODELO_DEFAULT,
        help=f"Directorio de salida para modelo y tokenizer (defecto: {SALIDA_MODELO_DEFAULT})",
    )
    parser.add_argument(
        "--modelo-base",
        type=str,
        default=MODELO_BASE_DEFAULT,
        help=f"Identificador del modelo base en HuggingFace (defecto: {MODELO_BASE_DEFAULT})",
    )
    parser.add_argument(
        "--prueba-rapida",
        action="store_true",
        help="Ejecuta una corrida corta de verificación con 50 ejemplos y 1 época.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Número de épocas de entrenamiento (defecto: 3).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Tamaño de lote para entrenamiento (defecto: 8).",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=3e-5,
        help="Tasa de aprendizaje (defecto: 3e-5).",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=42,
        help="Semilla determinista aleatoria (defecto: 42).",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=128,
        help="Longitud máxima de tokens por secuencia (defecto: 128).",
    )
    parser.add_argument(
        "--salida-metricas",
        type=str,
        default=None,
        help="Ruta opcional para guardar el JSON con métricas de la partición de prueba.",
    )
    parser.add_argument(
        "--no-eval-test",
        action="store_true",
        help="Deshabilita la evaluación sobre la partición de prueba al terminar el entrenamiento.",
    )
    parser.add_argument(
        "--demostracion",
        type=str,
        default=None,
        help="Ruta a archivo JSON de transcripción para ejecutar demostración de clasificación.",
    )
    return parser


def main() -> int:
    """Punto de entrada de CLI."""
    parser = construir_parser_cli()
    args = parser.parse_args()

    if not _TORCH_DISPONIBLE:
        print(
            "[ERROR] PyTorch o Transformers no están disponibles en este entorno.\n"
            "El entrenamiento de mmBERT-small requiere instalar las siguientes dependencias:\n"
            "  pip install torch transformers datasets scikit-learn accelerate\n"
            "Para entrenar en la nube con GPU, utilice el notebook oficial:\n"
            "  entrenamiento/finetune_mmbert.ipynb",
            file=sys.stderr,
        )
        return 1

    try:
        entrenar_cpu(
            datos=args.datos,
            salida_dir=args.salida_modelo,
            modelo_base=args.modelo_base,
            prueba_rapida=args.prueba_rapida,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            semilla=args.semilla,
            max_length=args.max_length,
            evaluar_test=not args.no_eval_test,
            salida_metricas=args.salida_metricas,
        )

        if args.demostracion:
            demostrar_clasificacion_segmentos(
                modelo_dir=args.salida_modelo,
                ruta_transcripcion=args.demostracion,
                etiqueta_fuente="Archivo indicado por CLI",
            )

        print("[EXITO] Proceso de fine-tuning en CPU finalizado correctamente.")
        return 0
    except Exception as exc:
        print(f"[ERROR] Fallo durante el entrenamiento: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
