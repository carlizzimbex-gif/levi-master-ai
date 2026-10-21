# Levi Master AI — MVP

A responsive PWA frontend plus a FastAPI backend that performs real audio processing through FFmpeg.

## What works
- Master Only: upload a premixed track and process it.
- Mix & Master: upload instrumental + vocal stems, mix them, then master.
- WAV (24-bit PCM) and MP3 (320 kbps) exports.
- Basic controls: vocal gain, master loudness target, and output format.
- PWA manifest and service worker for installability.

## Requirements
- Python 3.10+
- FFmpeg and ffprobe installed and available on PATH
- Install backend packages: `pip install -r requirements.txt`

## Run on Windows
1. Install FFmpeg and add its `bin` folder to PATH.
2. Open PowerShell in this folder.
3. Run:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```
4. Open `http://localhost:8000`.

## Run on Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```
Then open http://localhost:8000.

## Notes
- This is a first functional prototype, not a guarantee of commercial mastering quality. Always audition the result on multiple systems before distribution.
- This app does not upload or store user accounts/projects permanently; generated files are temporary.
- For public deployment, add authentication, rate limits, private object storage, job queue, file-size limits, and automatic cleanup.
- FFmpeg must be installed separately; Python dependencies do not bundle it.
