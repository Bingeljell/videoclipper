# Video Shorts Clipper

Local CLI tool for downloading a video and generating short, timestamped clips from content you own or have rights to use.

## Requirements
- Python 3.11+
- `ffmpeg` available on PATH
- `yt-dlp` available on PATH 

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Single clip:

```bash
videoclipper <url> <start> <end>
videoclipper https://example.com/video 10 15
```

Multiple clips:

```bash
videoclipper <url> --clips "10-30,120-150" --outdir ./clips
```

Download once, clip many:

```bash
videoclipper download <url> --720p --outdir ./fullvideos
videoclipper clip ./fullvideos/<channel>_<title>.mp4 --clips "10-30,120-150"
```

Common options:
- `--outdir`: output directory (default: `./clips`).
- `--reencode`: frame-accurate clips (slower).
- `--480p` / `--720p` / `--1080p` / `--360p`: choose source quality (default: `--480p`).
- `--height 640`: choose an exact source height in pixels.
- `--format`: output container extension (default: `mp4`).

## Notes
- Fast mode uses stream copy and may cut on keyframes.
- Re-encode mode is slower but more accurate.
- If fast mode fails due to format mismatch, rerun with `--reencode` or choose a matching `--format`.
- If the requested quality is unavailable, the CLI prints the available heights for the video.
- Default output naming: `<channel>_<title>_<start>_<end>_<timestamp>.mp4` (sanitized ASCII).
- Downloads default to `./fullvideos` with `<channel>_<title>.<ext>` (timestamp is appended if the name exists).
- Use only with content you own or have permission to download.

## Roadmap
See `docs/ROADMAP.md`.

## License
MIT. See `LICENSE`.
