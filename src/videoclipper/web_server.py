"""FastAPI web server for videoclipper UI."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .clipper import (
    ClipperError,
    burn_captions,
    clip_source,
    clip_url,
    denoise_video,
    download_audio,
    download_url,
    get_local_info,
    get_info,
    compress_video,
    overlay_audio,
    parse_clip_ranges,
    parse_time,
)

# In-memory job tracking
jobs: dict[str, dict[str, Any]] = {}

BASE_DIR = Path("~/videoclipper").expanduser()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Clear old jobs on startup."""
    jobs.clear()
    yield


app = FastAPI(title="Video Clipper", lifespan=lifespan)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _generate_job_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_outdir(value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(value)
    return path.expanduser()


async def _save_upload(upload: UploadFile, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    destination = workdir / upload.filename
    with open(destination, "wb") as handle:
        handle.write(await upload.read())
    return destination


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Serve the main HTML page."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return _default_html()


@app.get("/api/routes")
async def api_routes() -> dict:
    """List all registered API routes for debugging."""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            if route.path.startswith("/api"):
                routes.append({"path": route.path, "methods": list(route.methods)})
    return {"routes": routes}


@app.get("/api/info")
async def api_info(url: str) -> dict:
    """Get video metadata and available qualities."""
    try:
        info = get_info(url)
        return {"success": True, **info}
    except ClipperError as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/info_local")
async def api_info_local(
    video: UploadFile | None = File(None),
    path: str | None = Form(None),
) -> dict:
    """Get metadata for a local file (upload or path)."""
    try:
        if video is not None:
            import tempfile

            with tempfile.TemporaryDirectory(prefix="videoclipper_info_") as tmp:
                workdir = Path(tmp)
                video_path = await _save_upload(video, workdir)
                info = get_local_info(video_path)
        elif path:
            info = get_local_info(Path(path))
        else:
            raise ClipperError("Provide a local file upload or path.")
        return {"success": True, **info}
    except ClipperError as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/download")
async def api_download(data: dict) -> dict:
    """Download a full video."""
    url = data.get("url", "")
    outdir = _resolve_outdir(data.get("outdir", str(BASE_DIR / "fullvideos")))
    quality_height = data.get("quality_height", 480)
    reencode = data.get("reencode", False)

    try:
        output = download_url(
            url=url,
            outdir=outdir,
            reencode=reencode,
            quality_height=quality_height,
        )
        return {"success": True, "path": str(output)}
    except ClipperError as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/audio")
async def api_audio(data: dict) -> dict:
    """Download audio only as MP3."""
    url = data.get("url", "")
    outdir = _resolve_outdir(data.get("outdir", str(BASE_DIR / "audio")))
    output_format = data.get("format", "mp3").strip().lstrip(".") or "mp3"

    try:
        output = download_audio(
            url=url,
            outdir=outdir,
            output_format=output_format,
        )
        return {"success": True, "path": str(output)}
    except ClipperError as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/overlay")
async def api_overlay(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    fade: float = 3.0,
) -> dict:
    """Overlay audio onto video with fade out."""
    import tempfile
    
    outdir = BASE_DIR / "overlay"
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded files to temp directory
    with tempfile.TemporaryDirectory(prefix="videoclipper_overlay_", dir=outdir) as tmp:
        workdir = Path(tmp)
        video_path = workdir / video.filename
        audio_path = workdir / audio.filename
        
        with open(video_path, "wb") as f:
            f.write(await video.read())
        with open(audio_path, "wb") as f:
            f.write(await audio.read())
        
        try:
            output = overlay_audio(
                video_path=video_path,
                audio_path=audio_path,
                outdir=outdir,
                fade_duration=fade,
            )
            return {"success": True, "path": str(output)}
        except ClipperError as exc:
            return {"success": False, "error": str(exc)}


@app.post("/api/denoise")
async def api_denoise(
    video: UploadFile = File(...),
    strength: float = 0.5,
) -> dict:
    """Reduce background noise in video audio."""
    import tempfile
    
    outdir = BASE_DIR / "denoised"
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file to temp directory
    with tempfile.TemporaryDirectory(prefix="videoclipper_denoise_", dir=outdir) as tmp:
        workdir = Path(tmp)
        video_path = workdir / video.filename
        
        with open(video_path, "wb") as f:
            f.write(await video.read())
        
        try:
            output = denoise_video(
                video_path=video_path,
                outdir=outdir,
                strength=strength,
            )
            return {"success": True, "path": str(output)}
        except ClipperError as exc:
            return {"success": False, "error": str(exc)}


@app.post("/api/captions")
async def api_captions(
    video: UploadFile = File(...),
    subtitles: UploadFile = File(...),
    font_size: int = 18,
    position: str = "bottom",
    bg_color: str = "#000000",
) -> dict:
    """Burn subtitles into video."""
    import tempfile
    
    outdir = BASE_DIR / "captioned"
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded files to temp directory
    with tempfile.TemporaryDirectory(prefix="videoclipper_captions_", dir=outdir) as tmp:
        workdir = Path(tmp)
        video_path = workdir / video.filename
        subtitle_path = workdir / subtitles.filename
        
        with open(video_path, "wb") as f:
            f.write(await video.read())
        with open(subtitle_path, "wb") as f:
            f.write(await subtitles.read())
        
        try:
            output = burn_captions(
                video_path=video_path,
                subtitle_path=subtitle_path,
                outdir=outdir,
                font_size=font_size,
                position=position,
                bg_color=bg_color,
            )
            return {"success": True, "path": str(output)}
        except ClipperError as exc:
            return {"success": False, "error": str(exc)}


@app.post("/api/clip_local")
async def api_clip_local(
    video: UploadFile | None = File(None),
    path: str | None = Form(None),
    clips: str = Form(""),
    outdir: str = Form(str(BASE_DIR / "clips")),
    reencode: str | bool | None = Form(False),
    output_format: str = Form("mp4"),
) -> dict:
    """Generate clips from a local video file (upload or path)."""
    try:
        ranges = parse_clip_ranges(clips)
        outdir_path = _resolve_outdir(outdir)
        outdir_path.mkdir(parents=True, exist_ok=True)
        output_format = output_format.strip().lstrip(".") or "mp4"
        if video is not None:
            import tempfile

            with tempfile.TemporaryDirectory(prefix="videoclipper_clip_", dir=outdir_path) as tmp:
                workdir = Path(tmp)
                video_path = await _save_upload(video, workdir)
                outputs = clip_source(
                    source=video_path,
                    ranges=ranges,
                    outdir=outdir_path,
                    reencode=_parse_bool(reencode),
                    output_format=output_format,
                )
        elif path:
            outputs = clip_source(
                source=Path(path),
                ranges=ranges,
                outdir=outdir_path,
                reencode=_parse_bool(reencode),
                output_format=output_format,
            )
        else:
            raise ClipperError("Provide a local file upload or path.")

        return {"success": True, "paths": [str(p) for p in outputs]}
    except ClipperError as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/compress")
async def api_compress(
    video: UploadFile | None = File(None),
    path: str | None = Form(None),
    outdir: str = Form(str(BASE_DIR / "compressed")),
    crf: int = Form(28),
    preset: str = Form("medium"),
    height: str | None = Form(None),
    output_format: str = Form("mp4"),
) -> dict:
    """Compress a local video file (upload or path)."""
    try:
        outdir_path = _resolve_outdir(outdir)
        outdir_path.mkdir(parents=True, exist_ok=True)
        output_format = output_format.strip().lstrip(".") or "mp4"
        height_value = int(height) if height else None
        if video is not None:
            import tempfile

            with tempfile.TemporaryDirectory(prefix="videoclipper_compress_", dir=outdir_path) as tmp:
                workdir = Path(tmp)
                video_path = await _save_upload(video, workdir)
                output = compress_video(
                    video_path=video_path,
                    outdir=outdir_path,
                    crf=int(crf),
                    preset=preset,
                    height=height_value,
                    output_format=output_format,
                )
        elif path:
            output = compress_video(
                video_path=Path(path),
                outdir=outdir_path,
                crf=int(crf),
                preset=preset,
                height=height_value,
                output_format=output_format,
            )
        else:
            raise ClipperError("Provide a local file upload or path.")

        return {"success": True, "path": str(output)}
    except (ClipperError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


@app.post("/api/clip")
async def api_clip(data: dict) -> dict:
    """Generate clips from a URL."""
    url = data.get("url", "")
    clips_str = data.get("clips", "")
    outdir = _resolve_outdir(data.get("outdir", str(BASE_DIR / "clips")))
    quality_height = data.get("quality_height", 480)
    reencode = data.get("reencode", False)
    output_format = data.get("format", "mp4").strip().lstrip(".") or "mp4"

    try:
        ranges = parse_clip_ranges(clips_str)
        source_path = Path(url)
        if source_path.exists():
            outputs = clip_source(
                source=source_path,
                ranges=ranges,
                outdir=outdir,
                reencode=reencode,
                output_format=output_format,
            )
        else:
            outputs = clip_url(
                url=url,
                ranges=ranges,
                outdir=outdir,
                reencode=reencode,
                output_format=output_format,
                quality_height=quality_height,
            )
        return {"success": True, "paths": [str(p) for p in outputs]}
    except ClipperError as exc:
        return {"success": False, "error": str(exc)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket for real-time job updates."""
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            action = data.get("action")

            if action == "start_clip":
                job_id = _generate_job_id()
                jobs[job_id] = {
                    "status": "starting",
                    "progress": 0,
                    "message": "Starting...",
                }
                await websocket.send_json({"type": "job_started", "job_id": job_id})

                # Start processing in background
                asyncio.create_task(
                    _process_clip_job(websocket, job_id, data.get("params", {}))
                )

            elif action == "get_status":
                job_id = data.get("job_id")
                if job_id in jobs:
                    await websocket.send_json(
                        {"type": "status", "job_id": job_id, **jobs[job_id]}
                    )

    except WebSocketDisconnect:
        pass


async def _process_clip_job(
    websocket: WebSocket, job_id: str, params: dict
) -> None:
    """Process a clip job and send progress updates."""
    url = params.get("url", "")
    clips_str = params.get("clips", "")
    outdir = _resolve_outdir(params.get("outdir", str(BASE_DIR / "clips")))
    quality_height = params.get("quality_height", 480)
    reencode = params.get("reencode", False)
    output_format = params.get("format", "mp4").strip().lstrip(".") or "mp4"

    async def send_progress(status: str, progress: int, message: str) -> None:
        jobs[job_id] = {"status": status, "progress": progress, "message": message}
        await websocket.send_json(
            {
                "type": "progress",
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "message": message,
            }
        )

    try:
        # Parse clip ranges
        await send_progress("parsing", 5, "Parsing clip ranges...")
        ranges = parse_clip_ranges(clips_str)

        # Download video
        await send_progress("downloading", 10, "Downloading video...")
        from tempfile import TemporaryDirectory

        with TemporaryDirectory(prefix="videoclipper_", dir=outdir) as tmp:
            workdir = Path(tmp)
            from .clipper import _inspect_formats, _available_heights, _clip_base_name
            from .clipper import _format_selector, _download_source

            data = _inspect_formats(url)
            h264_mp4, all_heights = _available_heights(data)
            available = all_heights if reencode else h264_mp4

            if quality_height not in available:
                raise ClipperError(
                    f"Requested {quality_height}p is not available. "
                    f"Available: {', '.join(str(h) for h in available)}"
                )

            format_selector, merge_format = _format_selector(quality_height, reencode)
            output_template = workdir / "source.%(ext)s"
            source = _download_source(url, output_template, format_selector, merge_format)

            await send_progress("processing", 50, f"Generating {len(ranges)} clip(s)...")

            # Generate clips
            from datetime import datetime
            from .clipper import _run_ffmpeg, _slugify

            base_name = _clip_base_name(data)
            run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            outputs: list[str] = []

            for i, (start, end) in enumerate(ranges):
                progress = 50 + int((i / len(ranges)) * 45)
                await send_progress(
                    "clipping", progress, f"Generating clip {i + 1}/{len(ranges)}..."
                )
                output_path = (
                    outdir / f"{base_name}_{start}_{end}_{run_stamp}.{output_format}"
                )
                _run_ffmpeg(source, start, end, output_path, reencode)
                outputs.append(str(output_path))

            await send_progress("complete", 100, "Done!")
            await websocket.send_json(
                {"type": "complete", "job_id": job_id, "outputs": outputs}
            )

    except ClipperError as exc:
        jobs[job_id] = {"status": "error", "error": str(exc)}
        await websocket.send_json(
            {"type": "error", "job_id": job_id, "error": str(exc)}
        )


def _default_html() -> str:
    """Return default HTML if static file doesn't exist."""
    return """<!DOCTYPE html>
<html>
<head><title>Video Clipper</title></head>
<body>
<h1>Video Clipper</h1>
<p>Static files not found. Please ensure the static directory exists.</p>
</body>
</html>"""


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
