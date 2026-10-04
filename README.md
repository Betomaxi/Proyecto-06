# Prompting Lab

Project 06 is a full-stack research tool for comparing LLM prompting techniques on a manually labeled support-intent dataset. It records raw predictions and computes accuracy per run and aggregate accuracy/standard deviation per technique.

## Current Closeout Status

The API, React workspace, dataset upload, experiment browsing/downloads, and a recorded Playwright walkthrough are implemented. The dataset currently contains 40 examples (20 Spanish and 20 English). The research result is **not ready for a final conclusion**: the latest completed experiment (`exp_1790798349_92639f67`) has 480 rows, all predicted as `invalid_response`, and reports 0.0 mean accuracy for all four techniques. Earlier completed experiments report 0.1 mean accuracy. Two experiment metadata records remain `running`. See the [project closeout checklist](docs/project-definition.md#13-cierre-y-estado-del-proyecto) before presenting results.

## Run Locally

Prerequisites: Python 3.10+, Node.js/npm, and (for model-backed evaluation) a reachable Ollama service or a supported OpenAI configuration.

### Backend

```powershell
cd Prompting-Lab/Backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env only when configuring a real model/provider.
uvicorn main:app --reload --host 127.0.0.1 --port 8111 --env-file .env
```

On macOS/Linux, activate with `source venv/bin/activate`. The default mock configuration needs no provider key. Verify the service at `http://127.0.0.1:8111/health`.

### Frontend

```powershell
cd Prompting-Lab/Frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. The frontend reads the API port from `Prompting-Lab/Frontend/config.js` (default `8111`).

### End-to-End Walkthrough

Start the backend first. Then:

```powershell
cd Prompting-Lab/E2ETests
npm install
npx playwright install chromium
npm run test:e2e
```

The walkthrough configures but does not submit an experiment, browses an existing completed experiment and downloads metadata, opens and cancels the delete confirmation, and uploads a temporary JSONL dataset which it removes afterward. It expects at least one completed experiment to already exist. Videos are written under `Prompting-Lab/E2ETests/test-results/`.

## Project Areas

- `Prompting-Lab/Backend/main.py`: FastAPI endpoints, model adapters, experiment execution, and metrics.
- `Prompting-Lab/Backend/datasets/dataset.jsonl`: 40-row bilingual sample dataset.
- `Prompting-Lab/Frontend/`: React/Vite run form, experiment history, file downloads, and dataset upload.
- `Prompting-Lab/E2ETests/`: Chromium UI walkthrough and video recording configuration.
- `docs/project-definition.md`: original assignment and the current closeout checklist.
- `docs/api_contract.md`: frontend-facing API contract.

## Research Closeout Gate

Do not report the currently stored metrics as a finding. First investigate why the saved model responses do not contain valid intent labels, reconcile the two stale `running` entries, verify the ground-truth annotations, and produce a supported comparison and explicit conclusion. A corrected evaluation is intentionally not launched by this closeout documentation update.