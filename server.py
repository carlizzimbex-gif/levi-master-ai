
import asyncio
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Levi Master AI")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = BASE_DIR / "Static"

WORK_DIR = BASE_DIR / "work"
OUT_DIR = BASE_DIR / "output"
WORK_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac",
    ".ogg", ".aiff", ".aif"
}

if not STATIC_DIR.exists():
    raise RuntimeError("A pasta static não foi encontrada.")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=500,
            detail="index.html não encontrado."
        )
    return index_file.read_text(encoding="utf-8")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
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
        raise HTTPException(
            status_code=400,
            detail="O áudio está vazio."
        )

    return destination


def number_value(value, name, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"Valor inválido: {name}."
        )

    if not minimum <= number <= maximum:
        raise HTTPException(
            status_code=400,
            detail=f"{name} deve estar entre {minimum} e {maximum}."
        )
    return number


# Presets de estilos musicais.
# Estes ajustes não são autotune nem correção de afinação.
STYLE_PRESET_ADJUSTMENTS = {
    "natural":  (0.0, 0.0, 0.0, 0.0, "natural"),
    "trap":     (1.2, 0.6, 1.0, 1.0, "modern"),
    "rap":      (0.5, 0.4, 1.2, 0.8, "modern"),
    "drill":    (1.5, 0.7, 1.1, 1.2, "modern"),
    "rnb":      (0.3, 0.5, 0.7, -0.5, "natural"),
    "afrobeat": (0.8, 0.8, 0.7, 0.0, "natural"),
    "pop":      (0.2, 0.6, 0.8, 0.2, "modern"),
}


def build_filter_chain(
    profile, target_lufs, bass, treble, presence, compression
):
    filters = ["highpass=f=25"]

    if bass:
        filters.append(
            f"equalizer=f=100:t=q:w=1:g={bass:.2f}"
        )

    if presence:
        filters.append(
            f"equalizer=f=3000:t=q:w=1:g={presence:.2f}"
        )

    if treble:
        filters.append(
            f"equalizer=f=10000:t=q:w=1:g={treble:.2f}"
        )

    if profile == "natural":
        ratio = 1.8 + compression * 0.22
        attack, release = 20, 180
    else:
        ratio = 2.5 + compression * 0.35
        attack, release = 8, 100
        filters.append(
            "equalizer=f=5000:t=q:w=1:g=0.5"
        )

    if compression > 0:
        threshold = -18 - compression * 0.6
        filters.append(
            f"acompressor=threshold={threshold:.2f}dB:"
            f"ratio={ratio:.2f}:attack={attack}:"
            f"release={release}:makeup=1"
        )

    filters.append(
        f"loudnorm=I={target_lufs:.1f}:TP=-1.0:LRA=11"
    )
    filters.append("alimiter=limit=0.891")

    return ",".join(filters)


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
            detail=(
                "O processamento demorou demasiado. "
                "Tenta um áudio mais curto."
            )
        )

    if result.returncode != 0:
        detail = (
            result.stderr or "Erro desconhecido do FFmpeg"
        )[-2500:]
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar áudio: {detail}"
        )

    return result


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
    style: str = Form("natural"),
    instrumental: UploadFile = File(None),
    vocals: UploadFile = File(None),
    track: UploadFile = File(None)
):
    if not shutil.which("ffmpeg"):
        raise HTTPException(
            status_code=500,
            detail=(
                "FFmpeg não está instalado ou "
                "não está disponível no servidor."
            )
        )

    if mode not in {"mix", "master"}:
        raise HTTPException(
            status_code=400,
            detail="Modo inválido."
        )

    if output_format not in {"wav", "mp3"}:
        raise HTTPException(
            status_code=400,
            detail="Formato de saída inválido."
        )

    if profile not in {"natural", "modern"}:
        raise HTTPException(
            status_code=400,
            detail="Perfil inválido."
        )

    if style not in STYLE_PRESET_ADJUSTMENTS:
        raise HTTPException(
            status_code=400,
            detail="Estilo musical inválido."
        )

    lufs = number_value(target_lufs, "LUFS", -18, -9)
    gain = number_value(vocal_gain, "Ganho vocal", -12, 12)
    bass_db = number_value(bass, "Graves", -6, 6)
    treble_db = number_value(treble, "Agudos", -6, 6)
    presence_db = number_value(presence, "Presença", -6, 6)
    comp = number_value(compression, "Compressão", 0, 10)

    # Aplicar os ajustes do estilo escolhido.
    (
        style_bass,
        style_treble,
        style_presence,
        style_comp,
        style_profile,
    ) = STYLE_PRESET_ADJUSTMENTS[style]

    bass_db = max(
        -6.0, min(6.0, bass_db + style_bass)
    )
    treble_db = max(
        -6.0, min(6.0, treble_db + style_treble)
    )
    presence_db = max(
        -6.0, min(6.0, presence_db + style_presence)
    )
    comp = max(
        0.0, min(10.0, comp + style_comp)
    )

    if style != "natural":
        profile = style_profile

    job_dir = WORK_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)

    output_path = (
        OUT_DIR / f"levi_master_{uuid.uuid4().hex}.{output_format}"
    )

    try:
        if mode == "mix":
            if instrumental is None or vocals is None:
                raise HTTPException(
                    status_code=400,
                    detail="Seleciona o instrumental e os vocais."
                )

            inst_suffix = Path(
                instrumental.filename or ""
            ).suffix.lower()

            vocal_suffix = Path(
                vocals.filename or ""
            ).suffix.lower()

            inst_path = await save_upload(
                instrumental,
                job_dir / f"instrumental{inst_suffix}"
            )

            vocal_path = await save_upload(
                vocals,
                job_dir / f"vocals{vocal_suffix}"
            )

            filters = build_filter_chain(
                profile,
                lufs,
                bass_db,
                treble_db,
                presence_db,
                comp
            )

            command = [
                "ffmpeg",
                "-y",
                "-i", str(inst_path),
                "-i", str(vocal_path),
                "-filter_complex",
                (
                    "[0:a]highpass=f=25[inst];"
                    f"[1:a]volume={gain:.2f}dB,"
                    "highpass=f=70[voc];"
                    "[inst][voc]"
                    "amix=inputs=2:duration=longest:"
                    f"dropout_transition=2,{filters}[out]"
                ),
                "-map", "[out]"
            ]

        else:
            if track is None:
                raise HTTPException(
                    status_code=400,
                    detail="Seleciona uma música para masterizar."
                )

            suffix = Path(
                track.filename or ""
            ).suffix.lower()

            track_path = await save_upload(
                track,
                job_dir / f"track{suffix}"
            )

            filters = build_filter_chain(
                profile,
                lufs,
                bass_db,
                treble_db,
                presence_db,
                comp
            )

            command = [
                "ffmpeg",
                "-y",
                "-i", str(track_path),
                "-af", filters
            ]

        if output_format == "wav":
            command += [
                "-c:a", "pcm_s24le",
                "-ar", "44100"
            ]
        else:
            command += [
                "-c:a", "libmp3lame",
                "-b:a", "320k",
                "-ar", "44100"
            ]

        command.append(str(output_path))

        await asyncio.to_thread(run_ffmpeg, command)

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            raise HTTPException(
                status_code=500,
                detail=(
                    "O servidor não conseguiu gerar "
                    "o áudio final."
                )
            )

        return FileResponse(
            path=str(output_path),
            media_type=(
                "audio/wav"
                if output_format == "wav"
                else "audio/mpeg"
            ),
            filename=f"levi-master-{style}.{output_format}",
            background=None
        )

    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
