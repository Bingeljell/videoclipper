# YouTube Clipper

Local CLI tool for downloading a YouTube video and generating timestamped clips.

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
youtubeclipper <url> <start> <end>
```

Multiple clips:

```bash
youtubeclipper <url> --clips "10-30,120-150" --outdir ./clips
```

Common options:
- `--outdir`: output directory (default: `./clips`).
- `--reencode`: frame-accurate clips (slower).
- `--format`: output container extension (default: `mp4`).

## Notes
- Fast mode uses stream copy and may cut on keyframes.
- Re-encode mode is slower but more accurate.
- If fast mode fails due to format mismatch, rerun with `--reencode` or choose a matching `--format`.
