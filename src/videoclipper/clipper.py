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


def _parse_time_unit(value: str) -> int:
    try:
        unit = int(value)
    except ValueError as exc:
        raise ClipperError(
            "Timestamps must be seconds (e.g., 120) or mm:ss or hh:mm:ss."
        ) from exc
    if unit < 0:
        raise ClipperError("Timestamps must be non-negative.")
    return unit


def parse_time(value: str) -> int:
    raw = value.strip()
    if not raw:
        raise ClipperError(
            "Timestamps must be seconds (e.g., 120) or mm:ss or hh:mm:ss."
        )

    parts = [part.strip() for part in raw.split(":")]
    if any(part == "" for part in parts):
        raise ClipperError(
            "Timestamps must be seconds (e.g., 120) or mm:ss or hh:mm:ss."
        )

    if len(parts) == 1:
        return _parse_time_unit(parts[0])
    if len(parts) == 2:
        minutes = _parse_time_unit(parts[0])
        seconds = _parse_time_unit(parts[1])
        if seconds >= 60:
            raise ClipperError("Seconds must be between 0 and 59.")
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours = _parse_time_unit(parts[0])
        minutes = _parse_time_unit(parts[1])
        seconds = _parse_time_unit(parts[2])
        if minutes >= 60:
            raise ClipperError("Minutes must be between 0 and 59.")
        if seconds >= 60:
            raise ClipperError("Seconds must be between 0 and 59.")
        return hours * 3600 + minutes * 60 + seconds

    raise ClipperError("Timestamps must be seconds (e.g., 120) or mm:ss or hh:mm:ss.")


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


_FFMPEG_HINT = (
    "ffmpeg is a system tool and cannot be installed with pip. "
    "Install it with `brew install ffmpeg` (macOS), "
    "`sudo apt install ffmpeg` (Debian/Ubuntu), or see https://ffmpeg.org/download.html."
)


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise ClipperError(f"Missing dependency on PATH: ffmpeg. {_FFMPEG_HINT}")


def _ensure_ffprobe() -> None:
    if shutil.which("ffprobe") is None:
        # ffprobe ships with ffmpeg, so the install instructions are the same.
        raise ClipperError(f"Missing dependency on PATH: ffprobe. {_FFMPEG_HINT}")


def _ensure_yt_dlp() -> None:
    if shutil.which("yt-dlp") is None:
        raise ClipperError(
            "Missing dependency on PATH: yt-dlp. Reinstall videoclipper "
            "(`pip install -e .`) or install it directly with "
            "`pipx install yt-dlp` / `pip install yt-dlp`."
        )


def _cookie_args(cookies_from_browser: str | None) -> list[str]:
    """Build yt-dlp cookie arguments for the given browser (e.g. 'chrome').

    Returns an empty list when no browser is requested. This lets yt-dlp read
    live cookies from the browser to satisfy sites (notably YouTube) that
    demand sign-in / bot verification.
    """
    if not cookies_from_browser:
        return []
    return ["--cookies-from-browser", cookies_from_browser.strip()]


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
    cookies_from_browser: str | None = None,
) -> Path:
    cmd = [
        "yt-dlp",
        "-f",
        format_selector,
        "-o",
        str(output_template),
        "--no-playlist",
        *_cookie_args(cookies_from_browser),
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


def _inspect_formats(url: str, cookies_from_browser: str | None = None) -> dict:
    cmd = [
        "yt-dlp",
        "-J",
        "--no-warnings",
        "--no-playlist",
        *_cookie_args(cookies_from_browser),
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


def _probe_media(path: Path) -> dict:
    _ensure_ffprobe()
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ClipperError(f"Failed to inspect media file: {path}") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClipperError("Failed to parse ffprobe output.") from exc


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 0:
        return "unknown"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


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


def get_info(url: str, cookies_from_browser: str | None = None) -> dict:
    _ensure_yt_dlp()
    data = _inspect_formats(url, cookies_from_browser=cookies_from_browser)
    h264_mp4, all_heights = _available_heights(data)
    duration = data.get("duration")
    return {
        "title": data.get("title") or "",
        "channel": data.get("channel") or data.get("uploader") or "",
        "video_id": data.get("id") or "",
        "duration_seconds": duration,
        "duration_text": _format_duration(duration),
        "h264_heights": h264_mp4,
        "all_heights": all_heights,
    }


def get_local_info(path: Path) -> dict:
    _ensure_ffmpeg()
    if not path.exists():
        raise ClipperError(f"Source file not found: {path}")
    if not path.is_file():
        raise ClipperError(f"Source path is not a file: {path}")

    data = _probe_media(path)
    streams = data.get("streams", [])
    format_data = data.get("format", {})
    duration = format_data.get("duration")
    try:
        duration_seconds = int(float(duration)) if duration is not None else None
    except ValueError:
        duration_seconds = None

    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    audio_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )

    height = video_stream.get("height") if video_stream else None
    width = video_stream.get("width") if video_stream else None
    vcodec = video_stream.get("codec_name") if video_stream else ""
    acodec = audio_stream.get("codec_name") if audio_stream else ""

    h264_heights = []
    all_heights = []
    if height:
        all_heights = [height]
        if vcodec == "h264" and path.suffix.lower() == ".mp4":
            h264_heights = [height]

    return {
        "title": path.name,
        "channel": "",
        "video_id": "",
        "duration_seconds": duration_seconds,
        "duration_text": _format_duration(duration_seconds),
        "h264_heights": h264_heights,
        "all_heights": all_heights,
        "width": width,
        "height": height,
        "video_codec": vcodec,
        "audio_codec": acodec,
    }




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
    cookies_from_browser: str | None = None,
) -> list[Path]:
    _ensure_ffmpeg()
    _ensure_yt_dlp()
    if quality_height <= 0:
        raise ClipperError("Quality height must be a positive integer.")

    outdir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="videoclipper_", dir=outdir) as tmp:
        workdir = Path(tmp)
        data = _inspect_formats(url, cookies_from_browser=cookies_from_browser)
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
        source = _download_source(
            url,
            output_template,
            format_selector,
            merge_format,
            cookies_from_browser=cookies_from_browser,
        )
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
    cookies_from_browser: str | None = None,
) -> Path:
    _ensure_yt_dlp()
    if quality_height <= 0:
        raise ClipperError("Quality height must be a positive integer.")

    outdir.mkdir(parents=True, exist_ok=True)

    data = _inspect_formats(url, cookies_from_browser=cookies_from_browser)
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
    return _download_source(
        url,
        output_template,
        format_selector,
        merge_format,
        cookies_from_browser=cookies_from_browser,
    )


def _get_best_audio_format(data: dict) -> str:
    """Get the format ID with the best audio quality that's likely to work.
    
    YouTube typically blocks audio-only (format 140) and high-quality video.
    We look for 720p or lower combined video+audio formats which usually have 
    good audio (128-160 kbps AAC) and are less likely to be blocked.
    """
    formats = data.get("formats", [])
    if not formats:
        return "worst"
    
    # Find formats with both video and audio (vcodec and acodec present)
    video_audio_formats = []
    for fmt in formats:
        height = fmt.get("height")
        vcodec = fmt.get("vcodec", "none")
        acodec = fmt.get("acodec", "none")
        format_id = fmt.get("format_id", "")
        abr = fmt.get("abr")  # Audio bitrate if available
        
        # Skip audio-only or video-only formats
        if not height or vcodec in (None, "none") or acodec in (None, "none"):
            continue
        
        # Skip very high resolutions (more likely to be blocked)
        if height > 720:
            continue
        
        video_audio_formats.append({
            "format_id": format_id,
            "height": height,
            "abr": abr or 0,
            "ext": fmt.get("ext", ""),
        })
    
    if not video_audio_formats:
        return "worst"
    
    # Sort by audio bitrate (descending), then by height (descending)
    # This prioritizes formats with better audio quality
    video_audio_formats.sort(key=lambda x: (x["abr"], x["height"]), reverse=True)
    
    # Return the format ID with best audio (usually 720p or 480p)
    return video_audio_formats[0]["format_id"]


def _audio_base_name(data: dict) -> str:
    """Generate a short base name for audio files (channel + timestamp only)."""
    channel = data.get("channel") or data.get("uploader") or ""
    channel_slug = _slugify(channel, 40) or "audio"
    return channel_slug


def download_audio(
    url: str,
    outdir: Path,
    output_format: str = "mp3",
    cookies_from_browser: str | None = None,
) -> Path:
    """Download audio from URL and convert to specified format (default: mp3).
    
    Since audio-only formats may be blocked, we download the lowest quality video
    (which includes audio) and extract the audio track.
    """
    _ensure_ffmpeg()
    _ensure_yt_dlp()

    outdir.mkdir(parents=True, exist_ok=True)

    # Get video info and find the worst quality format with both video and audio
    data = _inspect_formats(url, cookies_from_browser=cookies_from_browser)
    base_name = _audio_base_name(data)
    format_id = _get_best_audio_format(data)
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Download the selected format
    import tempfile
    with tempfile.TemporaryDirectory(prefix="videoclipper_audio_", dir=outdir) as tmp:
        workdir = Path(tmp)
        temp_video = workdir / f"temp_video_{run_stamp}.%(ext)s"
        
        download_cmd = [
            "yt-dlp",
            "-f",
            format_id,
            "--no-playlist",
            "-o",
            str(temp_video),
            *_cookie_args(cookies_from_browser),
            url,
        ]
        
        try:
            subprocess.run(download_cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            # Fall back to "worst" if specific format fails
            download_cmd[2] = "worst"
            try:
                subprocess.run(download_cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as exc2:
                stderr_msg = exc2.stderr.decode() if exc2.stderr else ""
                raise ClipperError(f"Failed to download video for audio extraction: {stderr_msg}") from exc2
        
        # Find the downloaded file
        pattern = temp_video.name.replace("%(ext)s", "*")
        candidates = sorted(workdir.glob(pattern.replace("*", "*")))
        if not candidates:
            raise ClipperError("Download succeeded but no video file was found.")
        
        downloaded_file = candidates[0]
        output_path = outdir / f"{base_name}_audio_{run_stamp}.{output_format}"
        
        # Extract audio with ffmpeg
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "ogg": "libvorbis",
            "flac": "flac",
            "wav": "pcm_s16le",
        }
        codec = codec_map.get(output_format, "copy")
        
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(downloaded_file),
            "-vn",  # No video
            "-c:a",
            codec,
            "-q:a",
            "2" if output_format == "mp3" else "0",
            str(output_path),
        ]
        
        _run_command(ffmpeg_cmd, f"Failed to extract audio to {output_format}.")

    return output_path


def _get_media_duration(path: Path) -> float:
    """Get the duration of a media file in seconds using ffprobe."""
    _ensure_ffprobe()
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise ClipperError(f"Failed to get duration of {path}") from exc


def overlay_audio(
    video_path: Path,
    audio_path: Path,
    outdir: Path,
    fade_duration: float = 3.0,
) -> Path:
    """Overlay an audio track onto a video.
    
    The audio will be trimmed to match the video length and faded out
    at the end to avoid abrupt cuts.
    """
    _ensure_ffmpeg()
    
    if not video_path.exists():
        raise ClipperError(f"Video file not found: {video_path}")
    if not audio_path.exists():
        raise ClipperError(f"Audio file not found: {audio_path}")
    
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Get durations
    video_duration = _get_media_duration(video_path)
    audio_duration = _get_media_duration(audio_path)
    
    # Calculate fade start time
    fade_start = max(0, video_duration - fade_duration)
    actual_fade_duration = min(fade_duration, video_duration)
    
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    base_name = _slugify(video_path.stem, 80) or "overlay"
    output_path = outdir / f"{base_name}_overlay_{run_stamp}.mp4"
    
    # Process audio and combine with video in one command
    # Trim audio to video length, apply fade out
    filter_complex = (
        f"[1:a]atrim=0:{video_duration},"
        f"afade=t=out:st={fade_start}:d={actual_fade_duration}[aout]"
    )
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "0:v:0",  # Video from first input
        "-map",
        "[aout]",  # Processed audio
        "-c:v",
        "copy",  # Copy video stream (no re-encode)
        "-c:a",
        "aac",  # Re-encode audio to AAC
        "-b:a",
        "192k",  # Good quality audio
        "-shortest",  # Ensure output matches shortest input
        str(output_path),
    ]
    
    _run_command(cmd, "Failed to overlay audio onto video.")
    
    return output_path


def denoise_video(
    video_path: Path,
    outdir: Path,
    strength: float = 0.5,
) -> Path:
    """Reduce background noise in a video's audio using FFT denoising.
    
    Args:
        video_path: Path to the video file
        outdir: Directory to save the output
        strength: Noise reduction strength (0.0 to 1.0, where 0.5 is moderate)
    """
    _ensure_ffmpeg()
    
    if not video_path.exists():
        raise ClipperError(f"Video file not found: {video_path}")
    if not video_path.is_file():
        raise ClipperError(f"Path is not a file: {video_path}")
    
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Map strength (0.0-1.0) to afftdn noise floor (-80 to -20 dB)
    # Higher strength = more aggressive noise reduction (less negative value)
    noise_floor = -80 + (strength * 60)  # Range: -80 (light) to -20 (heavy)
    
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    base_name = _slugify(video_path.stem, 80) or "denoised"
    output_path = outdir / f"{base_name}_denoised_{run_stamp}.mp4"
    
    # Use afftdn filter for FFT-based noise reduction
    # nf = noise floor, track_noise = track noise automatically
    audio_filter = f"afftdn=nf={noise_floor:.1f}:tn=1"
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
        "-c:v",
        "copy",  # Copy video stream (no re-encode)
        "-c:a",
        "aac",  # Re-encode audio with denoising
        "-b:a",
        "192k",  # Good quality audio
        "-af",
        audio_filter,
        str(output_path),
    ]
    
    _run_command(cmd, "Failed to denoise video audio.")
    
    return output_path


def compress_video(
    video_path: Path,
    outdir: Path,
    crf: int = 28,
    preset: str = "medium",
    height: int | None = None,
    output_format: str = "mp4",
) -> Path:
    """Compress a local video using H.264 + AAC.

    Args:
        video_path: Path to the video file
        outdir: Directory to save the output
        crf: Quality factor (lower = higher quality, larger file). Typical 18-30.
        preset: ffmpeg preset (e.g., veryfast, fast, medium, slow)
        height: Optional output height (maintains aspect ratio)
        output_format: Output container extension (default: mp4)
    """
    _ensure_ffmpeg()

    if not video_path.exists():
        raise ClipperError(f"Video file not found: {video_path}")
    if not video_path.is_file():
        raise ClipperError(f"Path is not a file: {video_path}")
    if crf < 0 or crf > 51:
        raise ClipperError("CRF must be between 0 and 51.")
    if height is not None and height <= 0:
        raise ClipperError("Height must be a positive integer.")

    outdir.mkdir(parents=True, exist_ok=True)

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    base_name = _slugify(video_path.stem, 80) or "compressed"
    output_path = outdir / f"{base_name}_compressed_{run_stamp}.{output_format}"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
    ]
    if height is not None:
        cmd.extend(["-vf", f"scale=-2:{height}"])
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )

    _run_command(cmd, "Failed to compress video.")

    return output_path


def burn_captions(
    video_path: Path,
    subtitle_path: Path,
    outdir: Path,
    font_size: int = 18,
    position: str = "bottom",
    bg_color: str = "#000000",
) -> Path:
    """Burn subtitles into a video using ffmpeg.
    
    Args:
        video_path: Path to the video file
        subtitle_path: Path to the subtitle file (SRT, VTT, ASS)
        outdir: Directory to save the output
        font_size: Font size for the subtitles (default: 18)
        position: Position of subtitles - "bottom", "top", "center" (default: "bottom")
        bg_color: Background color in hex (default: "#000000" for black)
    """
    _ensure_ffmpeg()
    
    if not video_path.exists():
        raise ClipperError(f"Video file not found: {video_path}")
    if not subtitle_path.exists():
        raise ClipperError(f"Subtitle file not found: {subtitle_path}")
    
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Map position to ASS alignment values
    position_map = {
        "bottom": "2",  # Bottom center
        "top": "6",     # Top center
        "center": "5",  # Center
    }
    alignment = position_map.get(position, "2")
    
    # Convert hex color to ASS format (&HAABBGGRR)
    # Remove # and convert to BGR format with alpha
    bg_color_clean = bg_color.lstrip("#")
    if len(bg_color_clean) == 8:
        # Already has alpha (e.g., #80000000)
        a = bg_color_clean[0:2]
        r = bg_color_clean[2:4]
        g = bg_color_clean[4:6]
        b = bg_color_clean[6:8]
        bg_color_ass = f"&H{a}{b}{g}{r}"
    elif len(bg_color_clean) == 6:
        # No alpha, add 80 (50% transparent)
        r = bg_color_clean[0:2]
        g = bg_color_clean[2:4]
        b = bg_color_clean[4:6]
        bg_color_ass = f"&H80{b}{g}{r}"
    else:
        bg_color_ass = "&H80000000"  # Default semi-transparent black
    
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    base_name = _slugify(video_path.stem, 80) or "captioned"
    output_path = outdir / f"{base_name}_captioned_{run_stamp}.mp4"
    
    # Use ffmpeg to burn subtitles with styling
    # Force_style allows customization of subtitle appearance
    # PrimaryColour = white text (&H00FFFFFF)
    # OutlineColour = black outline (&HFF000000) for contrast
    # BackColour = semi-transparent background
    filter_str = (
        f"subtitles='{str(subtitle_path).replace(':', '\\:')}':"
        f"force_style='FontSize={font_size},Alignment={alignment},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&HFF000000,BackColour={bg_color_ass},Outline=2,Shadow=0,MarginV=20,"
        f"BorderStyle=4'"
    )
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        filter_str,
        "-c:a",
        "copy",  # Copy audio without re-encoding
        "-c:v",
        "libx264",  # Re-encode video with subtitles
        "-preset",
        "medium",  # Balance between speed and quality
        "-crf",
        "23",  # Good quality
        str(output_path),
    ]
    
    _run_command(cmd, "Failed to burn captions into video.")
    
    return output_path


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
