import os, shutil, subprocess, tempfile, uuid
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent

STATIC_DIR = BASE / "static"
if not STATIC_DIR.is_dir():
    STATIC_DIR = BASE / "Static"

OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

app = FastAPI(title="Levi Master AI", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(500, "FFmpeg/ffprobe não encontrados. Instala o FFmpeg e adiciona-o ao PATH.")

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise HTTPException(422, "Não foi possível processar este áudio. Confirma o ficheiro e tenta novamente. " + (p.stderr[-700:] if p.stderr else ""))

def save_upload(upload: UploadFile, target: Path):
    if not upload or not upload.filename:
        raise HTTPException(400, "Ficheiro em falta.")
    allowed = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".aiff", ".aif"}
    if Path(upload.filename).suffix.lower() not in allowed:
        raise HTTPException(400, "Formato não suportado. Usa WAV, MP3, FLAC, M4A, AAC, OGG ou AIFF.")
    data = upload.file.read()
    if not data:
        raise HTTPException(400, "O ficheiro enviado está vazio.")
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(413, "O ficheiro excede o limite de 200 MB.")
    target.write_bytes(data)

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg_available": bool(shutil.which("ffmpeg"))}

@app.post("/api/process")
async def process_audio(
    mode: str = Form(...),
    output_format: str = Form("wav"),
    target_lufs: float = Form(-14.0),
    vocal_gain: float = Form(0.0),
    track: UploadFile = File(None),
    instrumental: UploadFile = File(None),
    vocals: UploadFile = File(None),
):
    require_ffmpeg()
    if output_format not in ("wav", "mp3"):
        raise HTTPException(400, "Formato de saída inválido.")
    if not (-18 <= target_lufs <= -9):
        raise HTTPException(400, "O alvo de loudness deve estar entre -18 e -9 LUFS.")
    job = uuid.uuid4().hex
    work = Path(tempfile.mkdtemp(prefix="levimaster_"))
    try:
        mixed = work / "mix.wav"
        if mode == "master":
            src = work / "source"
            save_upload(track, src)
            # Decode to a clean PCM intermediate; master chain runs on the server.
            run(["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_f32le", str(mixed)])
        elif mode == "mix":
            inst = work / "instrumental"
            vox = work / "vocals"
            save_upload(instrumental, inst)
            save_upload(vocals, vox)
            # Vocal gain and a light high-pass reduce rumble; amix aligns to the longer stem.
            filt = f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo[inst];[1:a]volume={max(-12,min(12,float(vocal_gain)))}dB,highpass=f=70,aformat=sample_rates=44100:channel_layouts=stereo[vox];[inst][vox]amix=inputs=2:duration=longest:dropout_transition=2[m]"
            run(["ffmpeg", "-y", "-i", str(inst), "-i", str(vox), "-filter_complex", filt, "-map", "[m]", "-c:a", "pcm_f32le", str(mixed)])
        else:
            raise HTTPException(400, "Modo de processamento inválido.")

        output = OUT / f"levi_master_{job}.{output_format}"
        # Broad, conservative tonal shaping + loudness normalization + true-peak limiting.
        # loudnorm performs measured two-pass normalization internally in single-pass mode.
        chain = f"highpass=f=25,equalizer=f=250:t=q:w=1:g=-0.8,equalizer=f=3500:t=q:w=1:g=0.7,loudnorm=I={target_lufs}:TP=-1.0:LRA=11:print_format=summary,alimiter=limit=0.891"
        if output_format == "wav":
            run(["ffmpeg", "-y", "-i", str(mixed), "-af", chain, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s24le", str(output)])
            media = "audio/wav"
        else:
            run(["ffmpeg", "-y", "-i", str(mixed), "-af", chain, "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "320k", str(output)])
            media = "audio/mpeg"
        return FileResponse(output, media_type=media, filename=f"Levi_Master_AI_{job}.{output_format}", background=None)
    finally:
        shutil.rmtree(work, ignore_errors=True)

