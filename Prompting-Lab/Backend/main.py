import base64
import logging
import os
import uuid
import json
import time
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Any

import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

# Optional: import OpenAI client if available. If not present, the server will run in "mock" mode.
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# -------------------------
# Configuración y constantes
# -------------------------
APP_TITLE = "Project 06 — LLM Prompting Lab"
APP_DESCRIPTION = (
    "Empirical testing of prompting techniques (few-shot, CoT, role, zero-shot) "
    "on a custom dataset to measure performance variability."
)
API_VERSION = "1.0.0"

BASE_DIR = os.getenv("PROJECT_BASE_DIR", os.path.abspath(os.path.dirname(__file__)))
EXPERIMENTS_DIR = os.path.join(BASE_DIR, "experiments")
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")
os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
os.makedirs(DATASETS_DIR, exist_ok=True)

# Etiquetas definidas para la tarea (consistentes con la especificación)
LABELS = [
    "refund_request",
    "billing_issue",
    "upgrade_plan",
    "cancel_subscription",
    "technical_support",
    "feature_request",
    "account_access",
    "general_inquiry",
]

# Parámetros constantes para todas las técnicas
DEFAULT_PARAMS = {
    "temperature": 0.2,
    "max_tokens": 120,
    "top_p": 1.0,
    "n": 1,
}

# Plantillas de prompt (se usan tal cual; <TEXT> será reemplazado)
PROMPTS = {
    "zero_shot": (
        "Eres un clasificador que asigna una sola etiqueta de intención a un mensaje de cliente.\n"
        "Etiquetas posibles: " + ", ".join(LABELS) + ".\n"
        "Devuelve únicamente la etiqueta exacta (por ejemplo: refund_request).\n\n"
        "Mensaje: \"<TEXT>\"\n"
        "Respuesta:"
    ),
    "few_shot": (
        "Eres un clasificador que asigna una sola etiqueta de intención a un mensaje de cliente.\n"
        "Etiquetas posibles: " + ", ".join(LABELS) + ".\n"
        "Devuelve únicamente la etiqueta exacta.\n\n"
        "Ejemplos:\n"
        "\"Quiero cancelar mi suscripción a partir de este mes.\" -> cancel_subscription\n"
        "\"No puedo entrar a mi cuenta, me dice contraseña incorrecta.\" -> account_access\n"
        "\"Solicito reembolso por la compra duplicada de ayer.\" -> refund_request\n"
        "\"La factura de este mes tiene un cargo que no reconozco.\" -> billing_issue\n"
        "\"La app se cierra cuando intento subir una foto.\" -> technical_support\n\n"
        "Ahora clasifica:\n"
        "\"<TEXT>\"\n"
        "Respuesta:"
    ),
    "chain_of_thought": (
        "Eres un analista que razona paso a paso. Lee el mensaje y piensa en voz alta los pasos "
        "para identificar la intención principal (por ejemplo: identificar palabras clave, determinar si es reembolso, facturación, técnico, etc.). "
        "Después de tu razonamiento, en la última línea escribe SOLO la etiqueta exacta entre las siguientes: "
        + ", ".join(LABELS) + ".\n\n"
        "Mensaje: \"<TEXT>\"\n\n"
        "Razonamiento paso a paso:\n1.\n2.\n...\nEtiqueta final:"
    ),
    "role_prompting": (
        "Actúa como un analista de soporte senior. Tu tarea es leer el mensaje del cliente y devolver únicamente la etiqueta de intención que mejor lo describe. "
        "Usa estas etiquetas: " + ", ".join(LABELS) + ". No expliques nada más, solo la etiqueta exacta.\n\n"
        "Mensaje: \"<TEXT>\"\n"
        "Etiqueta:"
    ),
}

# -------------------------
# FastAPI app initialization
# -------------------------
app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=API_VERSION)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Pydantic models
# -------------------------
class RunExperimentRequest(BaseModel):
    dataset_path: Optional[str] = None  # path to JSONL dataset in server datasets dir
    dataset_upload: Optional[bool] = False  # if true, dataset must be uploaded via /datasets/upload first
    techniques: Optional[List[str]] = None  # subset of ["zero_shot","few_shot","chain_of_thought","role_prompting"]
    runs_per_technique: Optional[int] = 3
    model_name: Optional[str] = None  # model identifier (document for reproducibility)
    params: Optional[Dict[str, Any]] = None  # override DEFAULT_PARAMS


class ExperimentMetadata(BaseModel):
    experiment_id: str
    created_at: str
    dataset_path: str
    techniques: List[str]
    runs_per_technique: int
    model_name: Optional[str]
    params: Dict[str, Any]
    status: str  # pending, running, done, failed
    summary: Optional[Dict[str, Any]] = None
    end_time: Optional[str] = None  # Added to store the experiment end time
    
# -------------------------
# Utilities: dataset I/O, prompts, LLM wrapper, parsing, metrics
# -------------------------
def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    return lines


def save_jsonl(items: List[Dict[str, Any]], path: str):
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def ensure_valid_techniques(techniques: Optional[List[str]]) -> List[str]:
    allowed = ["zero_shot", "few_shot", "chain_of_thought", "role_prompting"]
    if not techniques:
        return allowed
    for t in techniques:
        if t not in allowed:
            raise HTTPException(status_code=400, detail=f"Técnica inválida: {t}")
    return techniques


def normalize_label(text: str) -> str:
    """
    Normaliza la respuesta del modelo para extraer una etiqueta válida.
    - strip, lower
    - buscar coincidencia exacta con LABELS
    - si no hay coincidencia, buscar la última palabra que coincida
    - si no hay coincidencia, devolver 'invalid_response'
    """
    if not text:
        return "invalid_response"
    s = text.strip().lower()
    # buscar etiqueta exacta en el texto
    for label in LABELS:
        if label in s.split():
            return label
    # buscar etiqueta como substring
    for label in LABELS:
        if label in s:
            return label
    # intentar extraer la última palabra
    tokens = [t.strip(" .,:;\"'") for t in s.split()]
    for tok in reversed(tokens):
        if tok in LABELS:
            return tok
    return "invalid_response"


def compute_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    df debe contener columnas: ground_truth, prediction
    Devuelve accuracy, precision/recall/f1 por etiqueta y confusion matrix.
    """
    y_true = df["ground_truth"].tolist()
    y_pred = df["prediction"].tolist()
    # map labels to indices for confusion matrix
    labels = LABELS.copy()
    # replace invalid_response with a special label if present
    if "invalid_response" in set(y_pred):
        if "invalid_response" not in labels:
            labels = labels + ["invalid_response"]
    acc = float(accuracy_score(y_true, y_pred))
    prf = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    precision = dict(zip(labels, prf[0].tolist()))
    recall = dict(zip(labels, prf[1].tolist()))
    f1 = dict(zip(labels, prf[2].tolist()))
    support = dict(zip(labels, prf[3].tolist()))
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    return {
        "accuracy": acc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
        "labels": labels,
        "confusion_matrix": cm,
    }


def save_metrics_json(metrics: Dict[str, Any], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


def save_json_atomically(data: Dict[str, Any], path: str):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


# -------------------------
# LLM wrapper (supports mock mode)
# -------------------------

def _parse_ollama_stream(resp):
    """
    Parsea respuestas de Ollama que pueden venir como NDJSON/stream.
    Devuelve la mejor cadena encontrada (campo 'response' si existe y concatenarlo, 
    o concatenación de 'thinking', o resp.text como fallback).
    """
    collected_thinking = []
    collected_response_field = []

    # iter_lines maneja streaming y NDJSON
    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        # intentar parsear JSON por línea
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # no es JSON: acumular texto crudo
            collected_thinking.append(line)
            continue

        if isinstance(obj, dict):
            # prioridad: campo 'response' en ollama responde con varios JSON responses (NDJSON/stream), hay que acumular 'thinking' incremental y hacer lo mismo para el response final.
            if obj.get("response"):
                collected_response_field.append(obj.get("response"))
            # acumular 'thinking' incremental si existe
            if obj.get("thinking"):
                collected_thinking.append(obj.get("thinking"))
            # si el stream indica done y ya tenemos response, podemos terminar
            if obj.get("done") is True and collected_response_field:
                break

    # Extracción final con prioridad
    if collected_response_field:
        return "".join(collected_response_field).strip()
    if collected_thinking:
        return "".join(collected_thinking).strip()
    # fallback: intentar parsear todo el body como JSON único
    try:
        full = resp.content.decode(resp.encoding or "utf-8", errors="ignore")
        parsed = json.loads(full)
        if isinstance(parsed, dict):
            return parsed.get("response") or parsed.get("text") or str(parsed)
        return str(parsed)
    except Exception:
        return resp.text or ""

def call_llm(prompt: str, model_name: Optional[str], params: Dict[str, Any]) -> str:
    """
    Llama a Ollama si OLLAMA_HOST está configurado; si no, intenta OpenAI; si tampoco, entra en MOCK MODE.
    Maneja respuestas NDJSON/stream de Ollama.
    """
    # 1) Intentar Ollama si está configurado
    ollama_host = os.getenv("OLLAMA_HOST")
    if ollama_host:
        ollama_model = model_name or os.getenv("OLLAMA_MODEL") or os.getenv("DEFAULT_MODEL_NAME") or "ollama-default"
        url = f"{ollama_host.rstrip('/')}/api/generate"
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("OLLAMA_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": ollama_model,
            "prompt": prompt,
            "temperature": params.get("temperature", 0.2),
            "max_tokens": params.get("max_tokens", 120),
            "top_p": params.get("top_p", 1.0),
            # si tu despliegue soporta flags adicionales, agrégalos aquí
        }
        try:
            # stream=True para recibir NDJSON/fragmentos
            resp = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
            resp.raise_for_status()
            # parsear robustamente el stream/NDJSON
            parsed = _parse_ollama_stream(resp)
            return parsed or ""
        except Exception as e:
            # registrar advertencia y continuar a fallback
            print(f"[WARN] Ollama call failed: {e}")
            try:
                # intentar mostrar fragmento para debugging sin exponer claves
                if 'resp' in locals():
                    snippet = resp.text[:1000]
                    print(f"[Dump] snippet: {snippet}")
            except Exception:
                pass
            # no raise: seguir a fallback

    # 2) Intentar OpenAI si está disponible y hay API key
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if OPENAI_AVAILABLE and api_key:
        openai.api_key = api_key
        try:
            response = openai.ChatCompletion.create(
                model=model_name or os.getenv("DEFAULT_MODEL_NAME", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.2),
                max_tokens=params.get("max_tokens", 120),
                top_p=params.get("top_p", 1.0),
                n=1,
            )
            return response["choices"][0]["message"]["content"]
        except Exception:
            try:
                response = openai.Completion.create(
                    model=model_name or os.getenv("DEFAULT_MODEL_NAME", "text-davinci-003"),
                    prompt=prompt,
                    temperature=params.get("temperature", 0.2),
                    max_tokens=params.get("max_tokens", 120),
                    top_p=params.get("top_p", 1.0),
                    n=1,
                )
                return response["choices"][0]["text"]
            except Exception as e:
                print(f"[WARN] OpenAI call failed: {e}")

    # 3) MOCK MODE determinista (sin costos)
    text = prompt.lower()
    rules = [
        (["cancel", "cancelar", "dar de baja"], "cancel_subscription"),
        (["reembolso", "devolución", "reembolsar", "reembolsen"], "refund_request"),
        (["factura", "facturación", "cargo", "cobro", "invoice", "billing"], "billing_issue"),
        (["actualizar", "upgrade", "cambiar al plan", "subir a pro", "actualizar al plan"], "upgrade_plan"),
        (["no puedo entrar", "contraseña", "password", "inactivo", "no puedo acceder"], "account_access"),
        (["error", "se cierra", "bug", "falla", "no funciona", "problema técnico", "error al"], "technical_support"),
        (["integración", "integrar", "slack", "feature", "añadir", "añadir integración", "exportación"], "feature_request"),
        (["demo", "descuento", "ofrecen", "pregunta", "cómo", "cómo puedo", "cuál es"], "general_inquiry"),
    ]
    for keywords, label in rules:
        for kw in keywords:
            if kw in text:
                return label
    return "general_inquiry"

# -------------------------
# Experiment execution logic
# -------------------------

def run_experiment_sync(
    dataset_path: str,
    techniques: List[str],
    runs_per_technique: int,
    model_name: Optional[str],
    params: Dict[str, Any],
    experiment_dir: str,
) -> Dict[str, Any]:
    """
    Ejecuta el experimento de forma síncrona y guarda resultados en experiment_dir.
    Retorna un resumen con métricas agregadas.
    """
    # Record start time
    start_time = datetime.utcnow().isoformat() + "Z"
    logger.info(f"Experiment {experiment_dir} started at: {start_time}")

    # Cargar dataset
    dataset = load_jsonl(dataset_path)
    # Validar estructura mínima
    for ex in dataset:
        if "id" not in ex or "text" not in ex or "ground_truth" not in ex:
            raise RuntimeError("Cada ejemplo debe tener 'id', 'text' y 'ground_truth'.")

    results_raw = []
    metrics_by_tech_run = []

    # Iterar técnicas y corridas
    for tech in techniques:
        prompt_template = PROMPTS.get(tech)
        if not prompt_template:
            raise RuntimeError(f"No existe prompt para la técnica {tech}")
        for run in range(1, runs_per_technique + 1):
            run_records = []
            for example in dataset:
                prompt = prompt_template.replace("<TEXT>", example["text"])
                # Llamada al LLM (o mock)
                try:
                    response_text = call_llm(prompt, model_name, params)
                except Exception as e:
                    response_text = f"__error__ {str(e)}"
                pred = normalize_label(response_text)
                record = {
                    "technique": tech,
                    "run": run,
                    "id": example["id"],
                    "text": example["text"],
                    "ground_truth": example["ground_truth"]["intent"],
                    "prediction": pred,
                    "raw_response": response_text,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
                results_raw.append(record)
                run_records.append(record)

            # Calcular métricas para esta técnica+run
            df_run = pd.DataFrame(run_records)
            metrics = compute_metrics(df_run)
            metrics_entry = {
                "technique": tech,
                "run": run,
                "metrics": metrics,
            }
            metrics_by_tech_run.append(metrics_entry)

    # Guardar resultados crudos y métricas
    raw_path = os.path.join(experiment_dir, "results_raw.jsonl")
    save_jsonl(results_raw, raw_path)
    metrics_path = os.path.join(experiment_dir, "metrics_by_tech_run.json")
    save_metrics_json({"metrics_by_tech_run": metrics_by_tech_run}, metrics_path)

    # Agregación por técnica (mean y std de accuracy)
    agg = {}
    for tech in techniques:
        accs = []
        for m in metrics_by_tech_run:
            if m["technique"] == tech:
                accs.append(m["metrics"]["accuracy"])
        if accs:
            agg[tech] = {"accuracy_mean": float(np.mean(accs)), "accuracy_std": float(np.std(accs)), "runs": len(accs)}
        else:
            agg[tech] = {"accuracy_mean": None, "accuracy_std": None, "runs": 0}
    agg_path = os.path.join(experiment_dir, "metrics_aggregated.json")
    save_metrics_json({"aggregated": agg}, agg_path)

    # Guardar CSV resumen por técnica/run
    rows = []
    for m in metrics_by_tech_run:
        rows.append({
            "technique": m["technique"],
            "run": m["run"],
            "accuracy": m["metrics"]["accuracy"],
        })
    df_summary = pd.DataFrame(rows)
    df_summary.to_csv(os.path.join(experiment_dir, "metrics_summary.csv"), index=False)

    return {
        "raw_path": raw_path,
        "metrics_path": metrics_path,
        "agg_path": agg_path,
        "summary_csv": os.path.join(experiment_dir, "metrics_summary.csv"),
        "aggregated": agg,
    }


# -------------------------
# API endpoints
# -------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/datasets/upload", summary="Subir dataset JSONL")
async def upload_dataset(file: UploadFile = File(...)):
    """
    Subir un archivo JSONL con el dataset. Se guarda en datasets/ con nombre único.
    """
    if not file.filename.endswith(".jsonl") and not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .jsonl o .json")
    dataset_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{file.filename}"
    dest_path = os.path.join(DATASETS_DIR, dataset_id)
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"dataset_path": dest_path, "filename": file.filename}


@app.get("/datasets/list", summary="Listar datasets disponibles")
def list_datasets():
    files = []
    for fname in os.listdir(DATASETS_DIR):
        path = os.path.join(DATASETS_DIR, fname)
        if os.path.isfile(path):
            files.append({"filename": fname, "path": path, "size": os.path.getsize(path)})
    return {"datasets": files}


@app.post("/experiments/run", summary="Iniciar un experimento (sincrónico o en background)")
def start_experiment(
    req: RunExperimentRequest,
    background_tasks: BackgroundTasks,
):
    """
    Inicia un experimento. Si dataset_path no se provee, se busca dataset.jsonl en datasets/.
    Ejecuta en background para no bloquear la petición.
    """
    techniques = ensure_valid_techniques(req.techniques)
    runs = int(req.runs_per_technique or 3)
    params = DEFAULT_PARAMS.copy()
    if req.params:
        params.update(req.params)
    model_name = req.model_name or os.getenv("DEFAULT_MODEL_NAME", "mock-model")

    # Resolver dataset path
    if req.dataset_path:
        dataset_path = req.dataset_path
        if not os.path.isabs(dataset_path):
            dataset_path = os.path.join(DATASETS_DIR, dataset_path)
        if not os.path.exists(dataset_path):
            raise HTTPException(status_code=404, detail="Dataset no encontrado en la ruta especificada.")
    else:
        # buscar dataset.jsonl por defecto
        default_candidates = [os.path.join(DATASETS_DIR, "dataset.jsonl")]
        found = None
        for c in default_candidates:
            if os.path.exists(c):
                found = c
                break
        if not found:
            raise HTTPException(status_code=400, detail="No se proporcionó dataset_path y no se encontró dataset por defecto.")
        dataset_path = found

    # Crear carpeta de experimento
    experiment_id = f"exp_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    experiment_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    os.makedirs(experiment_dir, exist_ok=True)

    # Guardar metadata inicial
    metadata = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime.utcnow().isoformat() + "Z",
        dataset_path=dataset_path,
        techniques=techniques,
        runs_per_technique=runs,
        model_name=model_name,
        params=params,
        status="pending",
        summary=None,
    )
    meta_path = os.path.join(experiment_dir, "metadata.json")
    save_json_atomically(metadata.model_dump(), meta_path)

    # Ejecutar en background
    def _bg_task():
        try:
            # 1. Set status to running
            metadata.status = "running"
            save_json_atomically(metadata.model_dump(), meta_path)

            # 2. Execute the experiment
            result = run_experiment_sync(
                dataset_path=dataset_path,
                techniques=techniques,
                runs_per_technique=runs,
                model_name=model_name,
                params=params,
                experiment_dir=experiment_dir,
            )

            # 3. Update metadata with summary and END TIME
            metadata.status = "done"
            metadata.summary = {
                "result_files": result,
                "aggregated": result.get("aggregated"),
            }
            # *** NEW: Record the end time ***
            metadata.end_time = datetime.utcnow().isoformat() + "Z"
            save_json_atomically(metadata.model_dump(), meta_path)
        except Exception as e:
            metadata.status = "failed"
            metadata.summary = {"error": str(e)}
            # *** NEW: Record the end time even on failure ***
            metadata.end_time = datetime.utcnow().isoformat() + "Z"
            save_json_atomically(metadata.model_dump(), meta_path)
    background_tasks.add_task(_bg_task)

    return {"experiment_id": experiment_id, "experiment_dir": experiment_dir, "status": "started"}


@app.get("/experiments/list", summary="Listar experimentos")
def list_experiments():
    try:
        exps = []
        for name in os.listdir(EXPERIMENTS_DIR):
            path = os.path.join(EXPERIMENTS_DIR, name)
            meta_path = os.path.join(path, "metadata.json")
            if not os.path.isdir(path) or not os.path.isfile(meta_path):
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if not isinstance(meta, dict):
                    raise ValueError("metadata must contain a JSON object")
            except (OSError, ValueError) as exc:
                logger.warning("Skipping invalid experiment metadata %s: %s", meta_path, exc)
                continue
            exps.append(meta)
        exps_sorted = sorted(
            exps,
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )
        return {"experiments": exps_sorted}
    except Exception as exc:
        logger.exception("Failed to list experiments in %s", EXPERIMENTS_DIR)
        raise HTTPException(status_code=500, detail="Failed to list experiments") from exc


@app.get("/experiments/{experiment_id}", summary="Obtener metadata de un experimento")
def get_experiment(experiment_id: str):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    meta_path = os.path.join(exp_dir, "metadata.json")
    if not os.path.isfile(meta_path):
        raise HTTPException(status_code=404, detail="Experimento no encontrado")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            raise ValueError("metadata must contain a JSON object")
        return meta
    except (OSError, ValueError) as exc:
        logger.exception("Failed to read experiment metadata %s", meta_path)
        raise HTTPException(status_code=500, detail="Experiment metadata is invalid") from exc


@app.get("/experiments/{experiment_id}/files", summary="Listar archivos de un experimento")
def list_experiment_files(experiment_id: str):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    if not os.path.isdir(exp_dir):
        raise HTTPException(status_code=404, detail="Experimento no encontrado")
    try:
        files = []
        for fname in os.listdir(exp_dir):
            path = os.path.join(exp_dir, fname)
            if os.path.isfile(path):
                files.append({"filename": fname, "path": path, "size": os.path.getsize(path)})
        return {"files": files}
    except OSError as exc:
        logger.exception("Failed to list files for experiment %s", experiment_id)
        raise HTTPException(status_code=500, detail="Failed to list experiment files") from exc


@app.get("/experiments/{experiment_id}/download", summary="Descargar archivo del experimento")
def download_experiment_file(experiment_id: str, filename: str):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    if not filename or os.path.basename(filename) != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(exp_dir, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return {
            "filename": filename,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
    except OSError as exc:
        logger.exception("Failed to download experiment file %s", file_path)
        raise HTTPException(status_code=500, detail="Failed to download experiment file") from exc


@app.post("/experiments/{experiment_id}/rerun", summary="Re-ejecutar experimento (misma configuración)")
def rerun_experiment(experiment_id: str, background_tasks: BackgroundTasks):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    meta_path = os.path.join(exp_dir, "metadata.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail="Experimento no encontrado")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    # crear nuevo experimento con misma configuración
    new_req = RunExperimentRequest(
        dataset_path=meta["dataset_path"],
        techniques=meta["techniques"],
        runs_per_technique=meta["runs_per_technique"],
        model_name=meta.get("model_name"),
        params=meta.get("params"),
    )
    return start_experiment(new_req, background_tasks)


@app.delete("/experiments/{experiment_id}", summary="Eliminar experimento y archivos")
def delete_experiment(experiment_id: str):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    if not os.path.exists(exp_dir):
        raise HTTPException(status_code=404, detail="Experimento no encontrado")
    shutil.rmtree(exp_dir)
    return {"deleted": experiment_id}


# -------------------------
# Helper: crear dataset de ejemplo si no existe (20 ejemplos)
# -------------------------
SAMPLE_DATASET_PATH = os.path.join(DATASETS_DIR, "dataset.jsonl")
if not os.path.exists(SAMPLE_DATASET_PATH):
    sample = [
        {"id":"I001","language":"es","text":"Quiero cancelar mi suscripción a partir de este mes.","ground_truth":{"intent":"cancel_subscription"},"annotator":"Roberto","notes":""},
        {"id":"I002","language":"es","text":"No puedo entrar a mi cuenta, me dice contraseña incorrecta.","ground_truth":{"intent":"account_access"},"annotator":"Roberto","notes":""},
        {"id":"I003","language":"es","text":"Solicito reembolso por la compra duplicada de ayer.","ground_truth":{"intent":"refund_request"},"annotator":"Roberto","notes":""},
        {"id":"I004","language":"es","text":"¿Cómo cambio al plan Pro y cuánto cuesta?","ground_truth":{"intent":"upgrade_plan"},"annotator":"Roberto","notes":""},
        {"id":"I005","language":"es","text":"La factura de este mes tiene un cargo que no reconozco.","ground_truth":{"intent":"billing_issue"},"annotator":"Roberto","notes":""},
        {"id":"I006","language":"es","text":"La app se cierra cuando intento subir una foto.","ground_truth":{"intent":"technical_support"},"annotator":"Roberto","notes":""},
        {"id":"I007","language":"es","text":"¿Pueden añadir integración con Slack?","ground_truth":{"intent":"feature_request"},"annotator":"Roberto","notes":""},
        {"id":"I008","language":"es","text":"Necesito cambiar la tarjeta de crédito asociada a mi cuenta.","ground_truth":{"intent":"billing_issue"},"annotator":"Roberto","notes":""},
        {"id":"I009","language":"es","text":"¿Ofrecen descuentos para equipos grandes?","ground_truth":{"intent":"general_inquiry"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Puede ser consulta comercial (sales) o general_inquiry; etiquetado como general_inquiry por falta de intención explícita de compra inmediata.\"}"},
        {"id":"I010","language":"es","text":"Mi usuario aparece como inactivo y no puedo acceder.","ground_truth":{"intent":"account_access"},"annotator":"Roberto","notes":""},
        {"id":"I011","language":"es","text":"Quiero que me devuelvan el dinero por el plan que no usé.","ground_truth":{"intent":"refund_request"},"annotator":"Roberto","notes":""},
        {"id":"I012","language":"es","text":"¿Puedo actualizar solo algunos usuarios al plan premium?","ground_truth":{"intent":"upgrade_plan"},"annotator":"Roberto","notes":""},
        {"id":"I013","language":"es","text":"Hay un error al generar reportes mensuales.","ground_truth":{"intent":"technical_support"},"annotator":"Roberto","notes":""},
        {"id":"I014","language":"es","text":"Deseo cancelar y que no me cobren el próximo ciclo.","ground_truth":{"intent":"cancel_subscription"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Menciona cancelación y evitar cobro; podría interpretarse también como solicitud de reembolso si ya fue cobrado. Se priorizó cancel_subscription según regla de prioridad.\"}"},
        {"id":"I015","language":"es","text":"¿Cómo puedo solicitar factura con RFC?","ground_truth":{"intent":"billing_issue"},"annotator":"Roberto","notes":"{\"tags\":[\"translated_note\"],\"annotator_comment\":\"Consulta fiscal específica; etiquetado como billing_issue. En traducción conservar 'RFC' como tax identifier.\"}"},
        {"id":"I016","language":"es","text":"Sería genial tener exportación a CSV automática.","ground_truth":{"intent":"feature_request"},"annotator":"Roberto","notes":""},
        {"id":"I017","language":"es","text":"¿Cuál es la diferencia entre los planes Básico y Pro?","ground_truth":{"intent":"general_inquiry"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Usuario pregunta por diferencias; podría implicar intención de upgrade, pero no la expresa explícitamente; etiquetado como general_inquiry.\"}"},
        {"id":"I018","language":"es","text":"Mi sesión expira constantemente y me desconecta.","ground_truth":{"intent":"technical_support"},"annotator":"Roberto","notes":""},
        {"id":"I019","language":"es","text":"Quiero cambiar el correo asociado a mi cuenta.","ground_truth":{"intent":"account_access"},"annotator":"Roberto","notes":""},
        {"id":"I020","language":"es","text":"¿Pueden ofrecer una demo para mi equipo?","ground_truth":{"intent":"general_inquiry"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Puede ser lead comercial o simple consulta; etiquetado como general_inquiry por no solicitar precio ni compromiso explícito.\"}"},
        {"id":"E001","language":"en","text":"I want to cancel my subscription starting this month.","ground_truth":{"intent":"cancel_subscription"},"annotator":"Roberto","notes":""},
        {"id":"E002","language":"en","text":"I can't log into my account, it says incorrect password.","ground_truth":{"intent":"account_access"},"annotator":"Roberto","notes":""},
        {"id":"E003","language":"en","text":"I request a refund for the duplicate purchase from yesterday.","ground_truth":{"intent":"refund_request"},"annotator":"Roberto","notes":""},
        {"id":"E004","language":"en","text":"How do I upgrade to the Pro plan and how much does it cost?","ground_truth":{"intent":"upgrade_plan"},"annotator":"Roberto","notes":""},
        {"id":"E005","language":"en","text":"This month's invoice has a charge I don't recognize.","ground_truth":{"intent":"billing_issue"},"annotator":"Roberto","notes":""},
        {"id":"E006","language":"en","text":"The app crashes when I try to upload a photo.","ground_truth":{"intent":"technical_support"},"annotator":"Roberto","notes":""},
        {"id":"E007","language":"en","text":"Can you add Slack integration?","ground_truth":{"intent":"feature_request"},"annotator":"Roberto","notes":""},
        {"id":"E008","language":"en","text":"I need to change the credit card associated with my account.","ground_truth":{"intent":"billing_issue"},"annotator":"Roberto","notes":""},
        {"id":"E009","language":"en","text":"Do you offer discounts for large teams?","ground_truth":{"intent":"general_inquiry"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Could be a sales inquiry or general question; labeled general_inquiry due to lack of explicit purchase intent.\"}"},
        {"id":"E010","language":"en","text":"My user appears inactive and I can't access it.","ground_truth":{"intent":"account_access"},"annotator":"Roberto","notes":""},
        {"id":"E011","language":"en","text":"I want a refund for the plan I didn't use.","ground_truth":{"intent":"refund_request"},"annotator":"Roberto","notes":""},
        {"id":"E012","language":"en","text":"Can I upgrade only some users to the premium plan?","ground_truth":{"intent":"upgrade_plan"},"annotator":"Roberto","notes":""},
        {"id":"E013","language":"en","text":"There is an error when generating monthly reports.","ground_truth":{"intent":"technical_support"},"annotator":"Roberto","notes":""},
        {"id":"E014","language":"en","text":"I want to cancel and not be charged next cycle.","ground_truth":{"intent":"cancel_subscription"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Mentions cancellation and avoiding charge; could imply refund if already charged. Prioritized cancel_subscription per annotation rules.\"}"},
        {"id":"E015","language":"en","text":"How can I request an invoice with tax ID (RFC)?","ground_truth":{"intent":"billing_issue"},"annotator":"Roberto","notes":"{\"tags\":[\"translated_note\"],\"annotator_comment\":\"Fiscal/tax invoice request; labeled billing_issue.\"}"},
        {"id":"E016","language":"en","text":"It would be great to have automatic CSV export.","ground_truth":{"intent":"feature_request"},"annotator":"Roberto","notes":""},
        {"id":"E017","language":"en","text":"What is the difference between the Basic and Pro plans?","ground_truth":{"intent":"general_inquiry"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"Could indicate upgrade intent but not explicit; labeled general_inquiry.\"}"},
        {"id":"E018","language":"en","text":"My session keeps expiring and disconnecting me.","ground_truth":{"intent":"technical_support"},"annotator":"Roberto","notes":""},
        {"id":"E019","language":"en","text":"I want to change the email associated with my account.","ground_truth":{"intent":"account_access"},"annotator":"Roberto","notes":""},
        {"id":"E020","language":"en","text":"Can you provide a demo for my team?","ground_truth":{"intent":"general_inquiry"},"annotator":"Roberto","notes":"{\"tags\":[\"ambiguous\"],\"annotator_comment\":\"May be a sales lead or general question; labeled general_inquiry due to no explicit purchase request.\"}"},
    ]
    save_jsonl(sample, SAMPLE_DATASET_PATH)

# -------------------------
# Run the application using uvicorn when executed directly
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8111))
    uvicorn.run(app, host="0.0.0.0", port=port)
