
Write-Host "--- Running Backend and Frontend Services --- Press Ctrl+C in the terminal windows to stop running processes." -ForegroundColor Cyan
cd Prompting-Lab/Backend; venv\Scripts\activate.bat; uvicorn main:app --reload --port 8111