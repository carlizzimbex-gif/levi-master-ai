import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).resolve().parent

# Aceita os dois nomes de pasta, respeitando maiúsculas/minúsculas.
if (BASE / "static").is_dir():
    STATIC_DIR = BASE / "static"
elif (BASE / "Static").is_dir():
    STATIC_DIR = BASE / "Static"
else:
    raise RuntimeError(
        "Pasta de ficheiros estáticos não encontrada. "
        "Cria uma pasta chamada static com index.html, app.js, "
        "style.css, manifest.json e sw.js."
    )

OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)

app = FastAPI(title="Levi Master AI", version="0.1.1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(
            status_code=500,
            detail="FFmpeg/ffprobe não encontrados no servidor."
        )


def run(cmd):
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="O processamento demorou demasiado tempo. Tenta um áudio menor."
        )

    if p.returncode != 0:
        detail = (p.stderr or "Erro desconhecido no FFmpeg.")[-1200:]
        raise HTTPException(
            status_code=422,
            detail="Não foi possível processar o áudio: " + detail
        )


def save_upload(upload: UploadFile, target: Path):
    if not upload or not upload.filename:
        raise HTTPException(status_code=400, detail="Ficheiro em falta.")

    allowed = {
        ".wav", ".mp3", ".flac", ".m4a",
        ".aac", ".ogg", ".aiff", ".aif"
    }

    if Path(upload.filename).suffix.lower() not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Usa WAV, MP3, FLAC, M4A, AAC, OGG ou AIFF."
        )

    data = upload.file.read()

    if not data:
        raise HTTPException(status_code=400, detail="O ficheiro enviado está vazio.")

    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="O ficheiro excede o limite de 200 MB."
        )

    target.write_bytes(data)


@app.get("/", response_class=HTMLResponse)
def home():
    index_file = STATIC_DIR / "index.html"

    if not index_file.is_file():
        raise HTTPException(
            status_code=500,
            detail="Não foi encontrado index.html na pasta de ficheiros estáticos."
        )

    return index_file.read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "ffprobe_available": bool(shutil.which("ffprobe")),
        "static_directory": STATIC_DIR.name
    }


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
        raise HTTPException(
            status_code=400,
            detail="Formato de saída inválido."
        )

    if not (-18 <= target_lufs <= -9):
        raise HTTPException(
            status_code=400,
            detail="O alvo de loudness deve estar entre -18 e -9 LUFS."
        )

    if not (-12 <= vocal_gain <= 12):
        raise HTTPException(
            status_code=400,
            detail="O ganho vocal deve estar entre -12 e +12 dB."
        )

    job = uuid.uuid4().hex
    work = Path(tempfile.mkdtemp(prefix="levimaster_"))

    try:
        mixed = work / "mix.wav"

        if mode == "master":
            src = work / "source"
            save_upload(track, src)

            run([
                "ffmpeg", "-y",
                "-i", str(src),
                "-vn",
                "-ac", "2",
                "-ar", "44100",
                "-c:a", "pcm_f32le",
                str(mixed)
            ])

        elif mode == "mix":
            inst = work / "instrumental"
            vox = work / "vocals"

            save_upload(instrumental, inst)
            save_upload(vocals, vox)

            filt = (
                "[0:a]"
                "aformat=sample_rates=44100:channel_layouts=stereo[inst];"
                f"[1:a]volume={vocal_gain}dB,"
                "highpass=f=70,"
                "aformat=sample_rates=44100:channel_layouts=stereo[vox];"
                "[inst][vox]"
                "amix=inputs=2:duration=longest:dropout_transition=2[m]"
            )

            run([
                "ffmpeg", "-y",
                "-i", str(inst),
                "-i", str(vox),
                "-filter_complex", filt,
                "-map", "[m]",
                "-c:a", "pcm_f32le",
                str(mixed)
            ])

        else:
            raise HTTPException(
                status_code=400,
                detail="Modo de processamento inválido."
            )

        output = OUT / f"levi_master_{job}.{output_format}"

        chain = (
            "highpass=f=25,"
            "equalizer=f=250:t=q:w=1:g=-0.8,"
            "equalizer=f=3500:t=q:w=1:g=0.7,"
            f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11,"
            "alimiter=limit=0.891"
        )

        if output_format == "wav":
            run([
                "ffmpeg", "-y",
                "-i", str(mixed),
                "-af", chain,
                "-ar", "44100",
                "-ac", "2",
                "-c:a", "pcm_s24le",
                str(output)
            ])
            media = "audio/wav"

        else:
            run([
                "ffmpeg", "-y",
                "-i", str(mixed),
                "-af", chain,
                "-ar", "44100",
                "-ac", "2",
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                str(output)
            ])
            media = "audio/mpeg"

        return FileResponse(
            path=output,
            media_type=media,
            filename=f"Levi_Master_AI_{job}.{output_format}",
            background=None
        )

    finally:
        shutil.rmtree(work, ignore_errors=True)
