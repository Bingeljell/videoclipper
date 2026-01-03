# Video Clipper App — MVP Spec Sheet

## 1) Goal
Build a simple tool that:

- Takes a video URL (supported by `yt-dlp`).
- Takes one or more clip ranges (start/end timestamps).
- Outputs MP4 clips locally (shorts).

MVP runs in CLI. Optional next step: local web UI.

## 2) MVP Feature Spec

### Inputs
- Video URL (supported by `yt-dlp`).
- Clip ranges.

Primary format: seconds (`120 150`).

Optional (later): accept `mm:ss` / `hh:mm:ss`.

Optional flags:
- Output directory.
- Output naming pattern.
- "Precise cut" mode (re-encode) vs "fast cut" (stream copy).

### Outputs
One or more MP4 files saved to disk:

- Default naming: `<channel>_<title>_<start>_<end>_<timestamp>.mp4`.
- If multiple clips: one file per range.

### Core User Stories
- As a user, I can generate a clip from a video URL by providing url + start + end.
- As a user, I can generate multiple clips in one run from the same URL.
- As a user, I can choose between fast clipping and frame-accurate clipping.

### CLI UX (MVP)
Command pattern (example):

```bash
videoclipper <url> <start> <end>
```

Multi-clip (example):

```bash
videoclipper <url> --clips "10-30,120-150,300-360"
```

Common options:
- `--outdir ./clips`
- `--reencode` (frame accurate)
- `--format mp4` (default mp4)

Optional two-step flow:

```bash
videoclipper download <url> --720p --outdir ./fullvideos
videoclipper clip ./fullvideos/<channel>_<title>.mp4 --clips "10-30,120-150"
```

### Processing Rules
Validate:
- URL format.
- `end > start`.
- Clip duration `> 0`.

Clip behavior:
- Fast mode (default): stream copy where possible (very fast; may cut on keyframes).
- Precise mode: re-encode for exact in/out (slower; accurate).

### Error Handling (MVP)
Clear messages for:
- Download failure / unavailable video.
- Invalid timestamps.
- Missing dependencies.

Return non-zero exit code on failure.

### Non-goals (MVP)
- Cloud hosting / sharing links.
- User accounts.
- In-browser playback editor.
- Automated highlight detection.

## 3) Optional “Local Web UI” (Phase 2)

### UI Features
Simple page with:
- URL input.
- Clip list builder (add/remove rows: start/end).
- Toggle: Fast vs Precise.
- “Generate Clips” button.
- Progress indication (basic).
- Download links to generated files (or show output path).

### Local-only constraints
- Runs on localhost.
- Files stored on local disk.
- No external database.

## 4) Tech Stack Recommendation

### MVP (CLI)
- Language: Python 3.11+.
- Video download: `yt-dlp` (CLI tool or Python wrapper).
- Video cutting/encoding: `ffmpeg`.
- CLI framework: `argparse` (minimal) or `typer` (nicer UX, optional).
- Packaging: pipx installable package, or simple script.
- OS support: macOS, Linux, Windows (FFmpeg + yt-dlp prerequisites).

### Phase 2 (Local Web UI)
- Backend: FastAPI (lightweight, modern).
- Frontend: simple HTML template (Jinja2) or minimal React if needed.
- Job execution: Python subprocess calls; optional background task queue.
- State: none required; ephemeral in-memory job tracking.

## 5) Architecture (High Level)

### Flow
- Parse inputs (URL + clip ranges).
- Download/resolve source video locally.
- For each clip range:
  - Generate clip via ffmpeg.
  - Write outputs + print file paths.

### Key Design Choices
- Separate "download" step from "clip" step (easier retries + multiple clips).
- Default to "fast mode" with an option for "precise mode".
- Keep outputs deterministic and predictable for scripting.

## 6) Security & Compliance Notes (Practical)
Treat this as a personal/local tool unless you’re ready to handle:
- Rights management.
- Source platform terms and licensing implications of downloading.
- Don’t store or transmit URLs/logs unless explicitly needed.

If you ever productize: add safeguards (allowed domains, rate limits, etc.).

## 7) Acceptance Criteria (MVP Done)
- CLI can generate a clip from a provided video URL + start/end.
- Can generate multiple clips in one command.
- Produces MP4 files playable in standard players.
- Clear errors for invalid ranges/dependency issues.
- Works on at least one target OS end-to-end.
