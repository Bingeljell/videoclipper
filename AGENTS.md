# Repository Guidelines

## Project Overview
This repository contains the MVP product spec and an initial Python CLI implementation for a local YouTube clipping tool. Use `spec.md` as the source of truth for scope, flags, and behavior.

## Project Structure & Module Organization
- `spec.md`: MVP requirements, CLI UX, and architecture notes.
- `src/youtubeclipper/`: CLI entry point and core clipping logic.
- `tests/`: pytest coverage for parsing and validation.
- `pyproject.toml`: packaging metadata and test configuration.
- `README.md`: setup and usage instructions.

## Build, Test, and Development Commands
Common commands for local development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

youtubeclipper <url> <start> <end>
youtubeclipper <url> --clips "10-30,120-150" --outdir ./clips

pytest
```

- `pip install -e .`: install the CLI locally for development.
- `youtubeclipper ...`: run the CLI with single or multiple clips.
- `pytest`: run parsing and validation tests.

## Coding Style & Naming Conventions
Follow these guidelines for consistency with the Python 3.11+ recommendation in `spec.md`:
- Indentation: 4 spaces, no tabs.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes.
- Files: lowercase with underscores (e.g., `clipper.py`).
- Keep CLI parsing separate from download/clip logic to match the architecture notes.

## Testing Guidelines
Tests use `pytest` and live under `tests/` with names like `test_clip_ranges.py`. Aim to cover input validation, clip range parsing, and fast vs precise modes.

## Commit & Pull Request Guidelines
There is no Git history to infer conventions. Use clear, imperative commit messages (e.g., "Add clip range parser"). For PRs, include:
- A short summary of changes.
- Testing notes (commands run or “not run”).
- Linked issues if applicable.
- Screenshots or GIFs for any future UI work.

## Security & Configuration Tips
This tool is intended for local use. Be explicit about dependencies (e.g., `ffmpeg`, `yt-dlp`), handle missing binaries with clear errors, and avoid logging sensitive URLs beyond what is necessary.
