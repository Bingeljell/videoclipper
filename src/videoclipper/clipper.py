from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
from typing import Iterable


class ClipperError(Exception):
    pass


def parse_time(value: str) -> int:
    value = value.strip()
    if ":" in value:
        raise ClipperError("Timestamps must be whole seconds (e.g., 120).")
    try:
        seconds = int(value)
    except ValueError as exc:
        raise ClipperError("Timestamps must be whole seconds (e.g., 120).") from exc
    if seconds < 0:
        raise ClipperError("Timestamps must be non-negative.")
    return seconds


def parse_clip_ranges(ranges: str) -> list[tuple[int, int]]:
    items = [item.strip() for item in ranges.split(",") if item.strip()]
    if not items:
        raise ClipperError("No clip ranges provided.")

    parsed: list[tuple[int, int]] = []
    for item in items:
        if "-" not in item:
            raise ClipperError(
                f"Invalid clip range '{item}'. Use the format start-end, e.g., 10-30."
            )
        start_text, end_text = item.split("-", 1)
        start = parse_time(start_text)
        end = parse_time(end_text)
        _validate_range(start, end)
        parsed.append((start, end))
    return parsed


def _validate_range(start: int, end: int) -> None:
    if end <= start:
        raise ClipperError("Clip end must be greater than start.")


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise ClipperError("Missing dependency on PATH: ffmpeg.")


def _ensure_yt_dlp() -> None:
    if shutil.which("yt-dlp") is None:
        raise ClipperError("Missing dependency on PATH: yt-dlp.")


def _run_command(cmd: Iterable[str], error_message: str) -> None:
    try:
        subprocess.run(list(cmd), check=True)
    except subprocess.CalledProcessError as exc:
        raise ClipperError(error_message) from exc


def _download_source(
    url: str,
    output_template: Path,
    format_selector: str,
    merge_output_format: str | None,
) -> Path:
    cmd = [
        "yt-dlp",
        "-f",
        format_selector,
        "-o",
        str(output_template),
        "--no-playlist",
    ]
    if merge_output_format:
        cmd.extend(["--merge-output-format", merge_output_format])
    cmd.append(url)
    _run_command(cmd, "Failed to download video with yt-dlp.")

    pattern = output_template.name.replace("%(ext)s", "*")
    candidates = sorted(output_template.parent.glob(pattern))
    if not candidates:
        raise ClipperError("Download succeeded but no source file was found.")
    return candidates[0]


def _inspect_formats(url: str) -> dict:
    cmd = [
        "yt-dlp",
        "-J",
        "--no-warnings",
        "--no-playlist",
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ClipperError("Failed to inspect available formats with yt-dlp.") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClipperError("Failed to parse format data from yt-dlp.") from exc


def _available_heights(data: dict) -> tuple[list[int], list[int]]:
    formats = data.get("formats", [])
    h264_mp4: set[int] = set()
    all_video: set[int] = set()
    for fmt in formats:
        height = fmt.get("height")
        vcodec = fmt.get("vcodec")
        if not height or vcodec in (None, "none"):
            continue
        all_video.add(height)
        if fmt.get("ext") != "mp4":
            continue
        if str(vcodec).startswith("avc1"):
            h264_mp4.add(height)
    return sorted(h264_mp4), sorted(all_video)


def _slugify(value: str, max_length: int) -> str:
    ascii_value = value.encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value).strip("_")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("_")
    return cleaned


def _clip_base_name(data: dict) -> str:
    channel = data.get("channel") or data.get("uploader") or ""
    title = data.get("title") or ""
    video_id = data.get("id") or ""
    channel_slug = _slugify(channel, 40)
    title_slug = _slugify(title, 80) or _slugify(video_id, 40)
    parts = [part for part in (channel_slug, title_slug) if part]
    return "_".join(parts) or "clip"




def _format_selector(height: int, reencode: bool) -> tuple[str, str | None]:
    if reencode:
        selector = f"bv*[height={height}]+ba/b[height={height}]"
        return selector, None
    selector = (
        "bv*[vcodec^=avc1][ext=mp4][height={height}]"
        "+ba[acodec^=mp4a]/b[ext=mp4][height={height}]"
    ).format(height=height)
    return selector, "mp4"


def _run_ffmpeg(
    source: Path,
    start: int,
    end: int,
    output_path: Path,
    reencode: bool,
) -> None:
    if output_path.exists():
        raise ClipperError(f"Output already exists: {output_path}")

    duration = end - start
    if reencode:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-n",
            "-i",
            str(source),
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-n",
            "-ss",
            str(start),
            "-i",
            str(source),
            "-t",
            str(duration),
            "-c",
            "copy",
            str(output_path),
        ]
    _run_command(cmd, "ffmpeg failed while generating clip.")


def clip_url(
    url: str,
    ranges: list[tuple[int, int]],
    outdir: Path,
    reencode: bool,
    output_format: str,
    quality_height: int,
) -> list[Path]:
    _ensure_ffmpeg()
    _ensure_yt_dlp()
    if quality_height <= 0:
        raise ClipperError("Quality height must be a positive integer.")

    outdir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="videoclipper_", dir=outdir) as tmp:
        workdir = Path(tmp)
        data = _inspect_formats(url)
        run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        h264_mp4, all_heights = _available_heights(data)
        base_name = _clip_base_name(data)
        available = all_heights if reencode else h264_mp4
        if quality_height not in available:
            if reencode:
                available_text = ", ".join(str(h) for h in available) or "none"
                raise ClipperError(
                    f"Requested {quality_height}p is not available. "
                    f"Available video heights: {available_text}. "
                    "Use --height to pick one of the available heights."
                )
            available_text = ", ".join(str(h) for h in available) or "none"
            other_text = ", ".join(str(h) for h in all_heights) or "none"
            raise ClipperError(
                f"Requested {quality_height}p is not available for fast clipping. "
                f"Available H.264 MP4 heights: {available_text}. "
                f"Other video heights: {other_text}. "
                "Use --height to choose an available H.264 MP4 height, or "
                "try --reencode for non-H.264 sources."
            )
        format_selector, merge_format = _format_selector(quality_height, reencode)
        output_template = workdir / "source.%(ext)s"
        source = _download_source(url, output_template, format_selector, merge_format)
        if not reencode and source.suffix.lstrip(".") != output_format:
            raise ClipperError(
                f"Source format '{source.suffix.lstrip('.')}' does not match "
                f"output '{output_format}'. Use --reencode or choose a matching --format."
            )
        for start, end in ranges:
            output_path = (
                outdir / f"{base_name}_{start}_{end}_{run_stamp}.{output_format}"
            )
            _run_ffmpeg(source, start, end, output_path, reencode)
            outputs.append(output_path)

    return outputs


def download_url(
    url: str,
    outdir: Path,
    reencode: bool,
    quality_height: int,
) -> Path:
    _ensure_yt_dlp()
    if quality_height <= 0:
        raise ClipperError("Quality height must be a positive integer.")

    outdir.mkdir(parents=True, exist_ok=True)

    data = _inspect_formats(url)
    h264_mp4, all_heights = _available_heights(data)
    available = all_heights if reencode else h264_mp4
    if quality_height not in available:
        if reencode:
            available_text = ", ".join(str(h) for h in available) or "none"
            raise ClipperError(
                f"Requested {quality_height}p is not available. "
                f"Available video heights: {available_text}. "
                "Use --height to pick one of the available heights."
            )
        available_text = ", ".join(str(h) for h in available) or "none"
        other_text = ", ".join(str(h) for h in all_heights) or "none"
        raise ClipperError(
            f"Requested {quality_height}p is not available for fast download. "
            f"Available H.264 MP4 heights: {available_text}. "
            f"Other video heights: {other_text}. "
            "Use --height to choose an available H.264 MP4 height, or "
            "try --reencode for non-H.264 sources."
        )

    format_selector, merge_format = _format_selector(quality_height, reencode)
    base_name = _clip_base_name(data)
    output_template = outdir / f"{base_name}.%(ext)s"
    if list(outdir.glob(f"{base_name}.*")):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_template = outdir / f"{base_name}_{stamp}.%(ext)s"
    return _download_source(url, output_template, format_selector, merge_format)


def clip_source(
    source: Path,
    ranges: list[tuple[int, int]],
    outdir: Path,
    reencode: bool,
    output_format: str,
) -> list[Path]:
    _ensure_ffmpeg()
    if not source.exists():
        raise ClipperError(f"Source file not found: {source}")
    if not source.is_file():
        raise ClipperError(f"Source path is not a file: {source}")

    outdir.mkdir(parents=True, exist_ok=True)

    base_name = _slugify(source.stem, 80) or "clip"
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    outputs: list[Path] = []
    for start, end in ranges:
        output_path = outdir / f"{base_name}_{start}_{end}_{run_stamp}.{output_format}"
        _run_ffmpeg(source, start, end, output_path, reencode)
        outputs.append(output_path)

    return outputs
