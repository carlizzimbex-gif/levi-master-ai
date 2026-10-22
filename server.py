
import os
import uuid
import shutil
import asyncio
import subprocess
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI(title="Levi Master AI")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = BASE_DIR / "Static"

WORK_DIR = BASE_DIR / "work"
OUT_DIR = BASE_DIR / "output"
WORK_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif"
}

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=500, detail="Ficheiro index.html não encontrado.")
    return index_file.read_text(encoding="utf-8")


@app.get("/api/health")
async def health():
    ffmpeg = shutil.which("ffmpeg")
    return {
        "status": "ok",
        "ffmpeg_available": bool(ffmpeg),
        "service": "Levi Master AI"
    }


async def save_upload(upload: UploadFile, destination: Path):
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {suffix or 'desconhecido'}."
        )

    total = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="O ficheiro excede o limite de 200 MB."
                    )
                output.write(chunk)
    finally:
        await upload.close()

    if total == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="O ficheiro enviado está vazio.")

    return destination


def run_ffmpeg(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="O processamento demorou demasiado tempo. Tenta um áudio mais curto."
        )

    if result.returncode != 0:
        detail = (result.stderr or "Erro desconhecido do FFmpeg")[-2500:]
        raise HTTPException(status_code=500, detail=f"Erro ao processar áudio: {detail}")

    return result


def number_value(value, name, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Valor inválido para {name}.")

    if not minimum <= number <= maximum:
        raise HTTPException(
            status_code=400,
            detail=f"{name} deve estar entre {minimum} e {maximum}."
        )

    return number


def build_filter_chain(mode, profile, target_lufs, bass, treble, presence, compression, vocal_gain):
    filters = ["highpass=f=25"]

    # EQ: valores limitados para evitar ajustes extremos.
    if bass != 0:
        filters.append(f"equalizer=f=100:t=q:w=1:g={bass:.2f}")
    if presence != 0:
        filters.append(f"equalizer=f=3000:t=q:w=1:g={presence:.2f}")
    if treble != 0:
        filters.append(f"equalizer=f=10000:t=q:w=1:g={treble:.2f}")

    if profile == "natural":
        ratio = 1.8 + compression * 0.22
        attack = 20
        release = 180
        peak = -1.0
    else:
        ratio = 2.5 + compression * 0.35
        attack = 8
        release = 100
        peak = -1.0
        # Presença ligeiramente maior no perfil moderno.
        filters.append("equalizer=f=5000:t=q:w=1:g=0.5")

    if compression > 0:
        threshold = -18 - compression * 0.6
        filters.append(
            f"acompressor=threshold={threshold:.2f}dB:"
            f"ratio={ratio:.2f}:attack={attack}:release={release}:"
            "makeup=1"
        )

    filters.append(
        f"loudnorm=I={target_lufs:.1f}:TP={peak:.1f}:LRA=11"
    )
    filters.append("alimiter=limit=0.891")
    return ",".join(filters)


@app.post("/api/process")
async def process_audio(
    mode: str = Form(...),
    output_format: str = Form("wav"),
    target_lufs: str = Form("-14"),
    vocal_gain: str = Form("0"),
    bass: str = Form("0"),
    treble: str = Form("0"),
    presence: str = Form("0"),
    compression: str = Form("4"),
    profile: str = Form("natural"),
    instrumental: UploadFile = File(None),
    vocals: UploadFile = File(None),
    track: UploadFile = File(None)
):
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=500, detail="FFmpeg não está disponível no servidor.")

    if mode not in {"mix", "master"}:
        raise HTTPException(status_code=400, detail="Modo inválido.")

    if output_format not in {"wav", "mp3"}:
        raise HTTPException(status_code=400, detail="Formato de saída inválido.")

    if profile not in {"natural", "modern"}:
        raise HTTPException(status_code=400, detail="Perfil de processamento inválido.")

    lufs = number_value(target_lufs, "LUFS", -18, -9)
    vocal_gain_db = number_value(vocal_gain, "Ganho vocal", -12, 12)
    bass_db = number_value(bass, "Graves", -6, 6)
    treble_db = number_value(treble, "Agudos", -6, 6)
    presence_db = number_value(presence, "Presença", -6, 6)
    compression_amount = number_value(compression, "Compressão", 0, 10)

    job_id = uuid.uuid4().hex
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    output_path = OUT_DIR / f"levi_master_{job_id}.{output_format}"

    try:
        if mode == "mix":
            if instrumental is None or vocals is None:
                raise HTTPException(
                    status_code=400,
                    detail="Para misturar, envia o instrumental e a voz."
                )

            instrumental_path = await save_upload(
                instrumental, job_dir / f"instrumental{Path(instrumental.filename or '').suffix.lower()}"
            )
            vocal_path = await save_upload(
                vocals, job_dir / f"vocals{Path(vocals.filename or '').suffix.lower()}"
            )

            filter_chain = build_filter_chain(
                mode, profile, lufs, bass_db, treble_db,
                presence_db, compression_amount, vocal_gain_db
            )

            command = [
                "ffmpeg", "-y",
                "-i", str(instrumental_path),
                "-i", str(vocal_path),
                "-filter_complex",
                (
                    f"[0:a]volume=1.0,highpass=f=25[inst];"
                    f"[1:a]volume={vocal_gain_db:.2f}dB,highpass=f=70[voc];"
                    f"[inst][voc]amix=inputs=2:duration=longest:dropout_transition=2,"
                    f"{filter_chain}[out]"
                ),
                "-map", "[out]",
            ]
        else:
            if track is None:
                raise HTTPException(status_code=400, detail="Envia um áudio para masterizar.")

            track_path = await save_upload(
                track, job_dir / f"track{Path(track.filename or '').suffix.lower()}"
            )

            filter_chain = build_filter_chain(
                mode, profile, lufs, bass_db, treble_db,
                presence_db, compression_amount, vocal_gain_db
            )

            command = [
                "ffmpeg", "-y",
                "-i", str(track_path),
                "-af", filter_chain,
            ]

        if output_format == "wav":
            command += ["-c:a", "pcm_s24le"]
        else:
            command += ["-c:a", "libmp3lame", "-b:a", "320k"]

        command.append(str(output_path))

        await asyncio.to_thread(run_ffmpeg, command)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="O servidor não gerou o áudio final.")

        return FileResponse(
            path=str(output_path),
            media_type="audio/wav" if output_format == "wav" else "audio/mpeg",
            filename=f"levi-master-{profile}.{output_format}"
        )

    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
