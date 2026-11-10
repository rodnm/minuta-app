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
) -> dict[str, Any]:
    """Ejecuta el pipeline de fine-tuning en CPU para mmBERT-small.

    Si prueba_rapida es True, reduce el dataset a 50 ejemplos y entrena 1 sola época
    para verificar que el flujo complete de punta a punta.
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

    print(f"[INFO] Cargando dataset sintético desde: {datos}")
    ejemplos = cargar_dataset_sintetico(datos)
    if not ejemplos:
        raise ValueError(f"No se encontraron ejemplos válidos en {datos}")

    if prueba_rapida:
        print("[INFO] Modo --prueba-rapida activo: limitando a 50 ejemplos para validación rápida.")
        random.shuffle(ejemplos)
        ejemplos = ejemplos[:50]
        epochs = min(epochs, 1)
        batch_size = min(batch_size, 4)

    # Distribución y pesos de clase
    etiquetas = [ex["etiqueta"] for ex in ejemplos]
    pesos_dict = calcular_pesos_clase(etiquetas)
    print(f"[INFO] Distribución de clases: {dict(Counter(etiquetas))}")
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

    # Split train/eval (80/20)
    random.shuffle(ejemplos)
    corte = max(1, int(len(ejemplos) * 0.8))
    train_items = ejemplos[:corte]
    eval_items = ejemplos[corte:] if len(ejemplos) > corte else ejemplos[:corte]

    ds_train = DatasetTexto(train_items, tokenizer, max_length)
    ds_eval = DatasetTexto(eval_items, tokenizer, max_length)

    salida_path = Path(salida_dir)
    salida_path.mkdir(parents=True, exist_ok=True)

    args_entrenamiento = TrainingArguments(
        output_dir=str(salida_path / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        logging_steps=5,
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

    print(f"[INFO] Iniciando entrenamiento en CPU ({len(train_items)} train, {len(eval_items)} eval, {epochs} epochs)...")
    trainer.train()

    print(f"[INFO] Guardando modelo y tokenizer en: {salida_path}")
    model.save_pretrained(str(salida_path))
    tokenizer.save_pretrained(str(salida_path))

    return {
        "total_ejemplos": len(ejemplos),
        "train_ejemplos": len(train_items),
        "eval_ejemplos": len(eval_items),
        "pesos_clase": pesos_dict,
        "salida_dir": str(salida_path),
        "status": "completado",
    }


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
        )
        print("[EXITO] Proceso de fine-tuning en CPU finalizado correctamente.")
        return 0
    except Exception as exc:
        print(f"[ERROR] Fallo durante el entrenamiento: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
