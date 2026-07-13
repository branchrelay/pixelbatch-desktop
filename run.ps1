if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Run .\build.ps1 first."
    exit 1
}

& .\.venv\Scripts\python.exe app.py

