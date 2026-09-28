# Prompting-Lab Project Overview

This repository contains a full-stack application project, structured into a Frontend (React/Vite) and a Backend (FastAPI).

## Project Context and Motivation
This project is dedicated to empirically testing prompting techniques (few-shot, chain-of-thought, zero-shot-CoT, role prompting) on a custom dataset to measure their quantitative performance. The core motivation is to move beyond subjective evaluation and measure the objective accuracy and variability of these techniques when applied to a specific task.

**Key Goal:** To design a controlled experiment where the prompting technique is the only variable, and the performance is measured against known ground truth.

## Core Methodology (Based on Project Definition)
1. **Dataset:** A custom dataset of at least 20 examples with manually verified, known correct answers (ground truth).
2. **Experimentation:** Applying at least 4 prompting techniques (Zero-shot, Few-shot, Chain-of-Thought, Role Prompting) to the same task and dataset.
3. **Variability Measurement:** Running a minimum of 3 trials for each technique to capture statistical variability, not just a single accuracy score.
4. **Reproducibility:** Ensuring the process is reproducible by keeping generation parameters (temperature, max_tokens) constant across all techniques.

## Project Structure
The project is organized under the `Prompting-Lab` directory:
*   **Frontend:** Located in `Prompting-Lab/Frontend/`, containing the React application code.
*   **Backend:** Located in `Prompting-Lab/Backend/`, containing the Python FastAPI application.
*   **E2E Tests:** Located in `Prompting-Lab/E2ETests/`, containing Playwright tests.

## Component Details

### Backend Details
The backend is a simple API service built with FastAPI:
*   **File:** `Prompting-Lab/Backend/main.py`

### Frontend Details
The frontend is a modern React application built with Vite:
*   **Dependencies:** Uses React and Vite for setup.
*   **Entry Point:** `Prompting-Lab/Frontend/src/main.jsx`
*   **Main Component:** `Prompting-Lab/Frontend/src/App.jsx`
*   **Assets:** Includes assets like `hero.png`, `react.svg`, and `vite.svg`.

## Testing
End-to-End tests are configured in:
*   `Prompting-Lab/E2ETests/playwright.config.ts`

## Project Exploration Summary
This repository is a full-stack project featuring a React/Vite Frontend, a FastAPI Backend, and Playwright E2E Tests. The structure is organized as follows:
*   **Frontend:** `Prompting-Lab/Frontend/` (React/Vite)
*   **Backend:** `Prompting-Lab/Backend/` (FastAPI)
*   **E2E Tests:** `Prompting-Lab/E2ETests/` (Playwright)

**Key Files to Note:**
*   `Frontend/src/App.jsx`: The main React component, which reads configuration from `config.js` to determine the backend port.
*   `Backend/main.py`: The FastAPI server running on port 8111.
*   `E2ETests/tests/example.spec.ts`: Playwright tests verifying the integration between the frontend and backend.

**Setup Notes:**

### Prerequisites
Ensure you have Node.js/npm (for Frontend), Python (for Backend), and Playwright installed on your system.

### 1. Backend Setup (FastAPI)
Navigate to the backend directory and set up the Python environment:

```bash
cd Prompting-Lab/Backend
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # Use '.\venv\Scripts\Activate.ps1' for Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

### 2. Frontend Setup (React/Vite)
Navigate to the frontend directory and install dependencies:

```bash
cd Prompting-Lab/Frontend
npm install
```

### 3. Run Frontend (Development Server)
Start the Vite development server to run the React application:

```bash
npm run dev
```

### 4. Run Backend (API Server) inside venv
Run the FastAPI application. You may need to set environment variables (e.g., in .env file):
```bash
uvicorn main:app --reload --port 8111
```

### 5. Run E2E Tests (Playwright)
Execute the end-to-end tests:

```bash
cd Prompting-Lab/E2ETests
# Run the tests
```