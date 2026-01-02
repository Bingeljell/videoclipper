from __future__ import annotations

from pathlib import Path
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


def _ensure_dependencies() -> None:
    missing = [name for name in ("ffmpeg", "yt-dlp") if shutil.which(name) is None]
    if missing:
        missing_list = ", ".join(missing)
        raise ClipperError(f"Missing dependencies on PATH: {missing_list}.")


def _run_command(cmd: Iterable[str], error_message: str) -> None:
    try:
        subprocess.run(list(cmd), check=True)
    except subprocess.CalledProcessError as exc:
        raise ClipperError(error_message) from exc


def _download_source(url: str, workdir: Path, format_selector: str) -> Path:
    output_template = workdir / "source.%(ext)s"
    cmd = [
        "yt-dlp",
        "-f",
        format_selector,
        "-o",
        str(output_template),
        url,
    ]
    _run_command(cmd, "Failed to download video with yt-dlp.")

    candidates = sorted(workdir.glob("source.*"))
    if not candidates:
        raise ClipperError("Download succeeded but no source file was found.")
    return candidates[0]


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
) -> list[Path]:
    _ensure_dependencies()

    outdir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="youtubeclipper_", dir=outdir) as tmp:
        workdir = Path(tmp)
        source_format = "best" if reencode else output_format
        source = _download_source(url, workdir, source_format)
        if not reencode and source.suffix.lstrip(".") != output_format:
            raise ClipperError(
                f"Source format '{source.suffix.lstrip('.')}' does not match "
                f"output '{output_format}'. Use --reencode or choose a matching --format."
            )
        for start, end in ranges:
            output_path = outdir / f"clip_{start}_{end}.{output_format}"
            _run_ffmpeg(source, start, end, output_path, reencode)
            outputs.append(output_path)

    return outputs
