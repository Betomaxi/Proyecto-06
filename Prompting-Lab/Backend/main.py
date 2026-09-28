import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI application
app = FastAPI(
    title="Project 06 — LLM Prompting Lab",
    description="Empirical testing of prompting techniques (few-shot, CoT, etc.) on a custom dataset to measure performance variability.",
    version="1.0.0",
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Run the application using uvicorn, reading the port from environment variables or defaulting to 8111
if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", 8111)))

