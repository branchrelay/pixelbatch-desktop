# GitHub Publishing Checklist

Use the `PixelBatch/` project folder as the repository root for a clean desktop-app repository.

## Include

- `app.py`
- `i18n.py`
- `theme.py`
- `modules/`
- `assets/icon.ico`
- `tests/`
- `examples/images.csv`
- `sample_prompts.csv`
- `requirements.txt`
- `PixelBatch.spec`
- `build.ps1`
- `run.ps1`
- `README.md`
- `LICENSE`
- `.gitignore`
- `.env.example`
- `SECURITY.md`

## Exclude

- `.env`, `.env.*`
- `.venv/`, `venv/`, `env/`
- `build/`, `dist/`
- `__pycache__/`, `.pytest_cache/`
- `settings.json`
- `logs/`, `cache/`, `temp/`, `tmp/`
- `input/`, `output/`, `uploads/`, `downloads/`, `processed/`, `generated/`, `results/`, `exports/`
- downloaded model files: `.u2net/`, `*.onnx`, `*.pth`, `*.bin`
- generated installers and binaries: `*.exe`
- local databases: `*.db`, `*.sqlite`, `*.sqlite3`

## Before first commit

```powershell
cd PixelBatch
git init
git status --short
python -m pytest -q
```

Review `git status` manually. No secret files, local settings, build artifacts, user CSV files, user images, or generated output should be staged.

## Private GitHub repository

```powershell
cd PixelBatch
git init
git add .
git status --short
git commit -m "Initial PixelBatch alpha release"
git branch -M main
git remote add origin https://github.com/<OWNER>/<PRIVATE_REPO>.git
git push -u origin main
```

Create the repository as private on GitHub before running `git push`.
