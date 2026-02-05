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

### Web UI (Recommended)

Launch the web interface for a visual clipping experience:

```bash
videoclipper web
```

Then open http://127.0.0.1:8000 in your browser. The web UI provides:
- Paste URLs and preview video info
- Clip local files via upload or local path
- Add multiple clip ranges with visual feedback
- Quality and format selection
- Real-time progress updates
- Output directory and filename customization
- Download audio only (MP3, WAV, AAC, OGG, FLAC)
- **Audio Overlay**: Upload a video and audio file to combine them with automatic fade-out
- **De-noise**: Upload a video to reduce background noise in the audio
- **Captions**: Upload a video and subtitle file (SRT/VTT/ASS) to burn captions into the video
- **Compress**: Upload a local video to reduce file size

Options:
```bash
videoclipper web --port 8080  # Use a different port
```

### CLI Usage

Single clip:

```bash
videoclipper <url> <start> <end>
videoclipper https://example.com/video 10 15
videoclipper https://example.com/video 1:30 2:10
videoclipper /path/to/video.mp4 10 15
```

Get video metadata and available qualities:

```bash
videoclipper <url> --getinfo
videoclipper /path/to/video.mp4 --getinfo
```

Multiple clips:

```bash
videoclipper <url> --clips "10-30,1:20-1:45,00:10:00-00:10:30" --outdir ./clips
```

Download once, clip many:

```bash
videoclipper download <url> --720p --outdir ./fullvideos
videoclipper clip ./fullvideos/<channel>_<title>.mp4 --clips "10-30,120-150"
```

Download audio only (as MP3):

```bash
videoclipper audio <url>
videoclipper audio <url> --format wav --outdir ./audio
```

Overlay audio onto video:

```bash
videoclipper overlay video.mp4 audio.mp3
videoclipper overlay video.mp4 audio.mp3 --fade 5 --outdir ./output
```

De-noise video audio (reduce background noise):

```bash
videoclipper denoise video.mp4
videoclipper denoise video.mp4 --strength 0.7 --outdir ./output
```

Burn captions/subtitles into video:

```bash
videoclipper captions video.mp4 subtitles.srt
videoclipper captions video.mp4 subtitles.srt --font-size 24 --position bottom --bg-color "#000000" --outdir ./output
```

Compress a local video:

```bash
videoclipper compress video.mp4 --crf 28 --preset medium --outdir ./compressed
videoclipper compress video.mp4 --height 720 --crf 30 --outdir ./compressed
```

Common options:
- `--outdir`: output directory (default: `./clips`).
- `--reencode`: frame-accurate clips (slower).
- `--480p` / `--720p` / `--1080p` / `--360p`: choose source quality (default: `--480p`).
- `--height 640`: choose an exact source height in pixels.
- `--format`: output container extension (default: `mp4`).
- `--getinfo`: print metadata and available heights without downloading.

## Notes
- Fast mode uses stream copy and may cut on keyframes.
- Re-encode mode is slower but more accurate.
- If fast mode fails due to format mismatch, rerun with `--reencode` or choose a matching `--format`.
- If the requested quality is unavailable, the CLI prints the available heights for the video.
- Default output naming: `<channel>_<title>_<start>_<end>_<timestamp>.mp4` (sanitized ASCII).
- Downloads default to `./fullvideos` with `<channel>_<title>.<ext>` (timestamp is appended if the name exists).
- Use only with content you own or have permission to download.
- Timestamps accept seconds, `mm:ss`, or `hh:mm:ss`.

## Roadmap
See `docs/ROADMAP.md`.

## License
MIT. See `LICENSE`.
