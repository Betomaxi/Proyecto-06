# Prompting Lab API Contract

Base URL: `http://127.0.0.1:8111`

The local FastAPI service enables CORS for the development UI. Errors use FastAPI's standard JSON shape, for example `{"detail":"Experimento no encontrado"}`. Paths and file sizes returned by the service are server-local filesystem values; clients should use `filename` for display and the download endpoint for file content.

## Health

`GET /health`

```json
{"status":"ok"}
```

## Datasets

`GET /datasets/list` returns files currently stored in the backend dataset directory:

```json
{
  "datasets": [
    {"filename":"dataset.jsonl","path":"<server path>","size":8900}
  ]
}
```

`POST /datasets/upload` accepts multipart form data with a `file` field. Files must end in `.jsonl` or `.json`.

```json
{"dataset_path":"<server path>","filename":"support-data.jsonl"}
```

Use the returned `filename` as `dataset_path` in a run request. The API does not currently provide a dataset-delete endpoint.

Each JSONL line must be a JSON object containing `id`, `text`, and `ground_truth.intent`. The repository sample additionally includes `language`, `annotator`, and `notes`.

## Run an Experiment

`POST /experiments/run` queues a background experiment. `dataset_path` may be omitted to use the default `datasets/dataset.jsonl`.

```json
{
  "dataset_path":"dataset.jsonl",
  "techniques":["zero_shot","few_shot","chain_of_thought","role_prompting"],
  "runs_per_technique":3,
  "model_name":"<configured-model-or-mock-model>",
  "params":{"temperature":0.2,"max_tokens":120,"top_p":1.0}
}
```

Allowed technique names are `zero_shot`, `few_shot`, `chain_of_thought`, and `role_prompting`. The immediate response is:

```json
{"experiment_id":"exp_<timestamp>_<id>","experiment_dir":"<server path>","status":"started"}
```

The response means the background job was queued, not completed. Poll `GET /experiments/{experiment_id}` for `status` (`pending`, `running`, `done`, or `failed`). Completed runs normally produce `metadata.json`, `results_raw.jsonl`, `metrics_by_tech_run.json`, `metrics_aggregated.json`, and `metrics_summary.csv`.

## Experiments

`GET /experiments/list` returns `{ "experiments": [<metadata>, ...] }`, newest first. Invalid or empty metadata files are logged and skipped so one damaged legacy folder does not fail the full listing.

`GET /experiments/{experiment_id}` returns the experiment metadata object. Metadata includes the experiment ID, timestamp, dataset path, techniques, run count, model, parameters, status, and (when available) result summary.

`GET /experiments/{experiment_id}/files` returns:

```json
{
  "files": [
    {"filename":"results_raw.jsonl","path":"<server path>","size":12345}
  ]
}
```

`GET /experiments/{experiment_id}/download?filename=results_raw.jsonl` returns the filename and a Base64-encoded file body:

```json
{"filename":"results_raw.jsonl","content_base64":"<base64>"}
```

The client must Base64-decode `content_base64` to reconstruct the original bytes. Filenames containing path separators are rejected.

`POST /experiments/{experiment_id}/rerun` queues another run using the saved configuration. `DELETE /experiments/{experiment_id}` permanently removes the experiment directory. The UI requires explicit confirmation and disables deletion while the status is pending or running.
