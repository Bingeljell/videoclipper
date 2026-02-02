from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clipper import (
    ClipperError,
    burn_captions,
    clip_source,
    clip_url,
    denoise_video,
    download_audio,
    download_url,
    get_info,
    overlay_audio,
    parse_clip_ranges,
    parse_time,
)
from .web_server import run_server


def _add_quality_flags(parser: argparse.ArgumentParser) -> None:
    quality_group = parser.add_mutually_exclusive_group()
    quality_group.add_argument(
        "--360p",
        dest="quality_height",
        action="store_const",
        const=360,
        help="Download 360p source (fast mode only works with H.264 MP4).",
    )
    quality_group.add_argument(
        "--480p",
        dest="quality_height",
        action="store_const",
        const=480,
        help="Download 480p source (default).",
    )
    quality_group.add_argument(
        "--720p",
        dest="quality_height",
        action="store_const",
        const=720,
        help="Download 720p source (fast mode only works with H.264 MP4).",
    )
    quality_group.add_argument(
        "--1080p",
        dest="quality_height",
        action="store_const",
        const=1080,
        help="Download 1080p source (fast mode only works with H.264 MP4).",
    )
    quality_group.add_argument(
        "--height",
        dest="quality_height",
        type=int,
        help="Download source at an exact height in pixels (fast mode needs H.264 MP4).",
    )
    parser.set_defaults(quality_height=480)


def _build_clip_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper",
        description="Download a video from a supported URL and generate clips.",
    )
    parser.add_argument("url", help="Video URL")
    parser.add_argument("start", nargs="?", help="Clip start time in seconds")
    parser.add_argument("end", nargs="?", help="Clip end time in seconds")
    parser.add_argument(
        "--clips",
        help='Comma-separated ranges like "10-30,120-150" (overrides start/end).',
    )
    parser.add_argument(
        "--getinfo",
        action="store_true",
        help="Print metadata and available qualities without downloading.",
    )
    parser.add_argument(
        "--outdir",
        default="clips",
        help="Directory to write clips (default: ./clips)",
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Re-encode for frame-accurate clips (slower)",
    )
    _add_quality_flags(parser)
    parser.add_argument(
        "--format",
        default="mp4",
        help="Output container extension (default: mp4)",
    )
    return parser


def _build_local_clip_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper clip",
        description="Generate clips from a local video file.",
    )
    parser.add_argument("source", help="Path to a local video file")
    parser.add_argument("start", nargs="?", help="Clip start time in seconds")
    parser.add_argument("end", nargs="?", help="Clip end time in seconds")
    parser.add_argument(
        "--clips",
        help='Comma-separated ranges like "10-30,120-150" (overrides start/end).',
    )
    parser.add_argument(
        "--outdir",
        default="clips",
        help="Directory to write clips (default: ./clips)",
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Re-encode for frame-accurate clips (slower)",
    )
    parser.add_argument(
        "--format",
        default="mp4",
        help="Output container extension (default: mp4)",
    )
    return parser


def _build_download_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper download",
        description="Download a video from a supported URL for reuse.",
    )
    parser.add_argument("url", help="Video URL")
    parser.add_argument(
        "--outdir",
        default="fullvideos",
        help="Directory to save full videos (default: ./fullvideos)",
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="Allow non-H.264 sources for higher quality downloads.",
    )
    _add_quality_flags(parser)
    return parser


def _build_web_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper web",
        description="Launch the web UI for video clipping.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )
    return parser


def _build_audio_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper audio",
        description="Download audio from a supported URL as MP3.",
    )
    parser.add_argument("url", help="Video URL")
    parser.add_argument(
        "--outdir",
        default="audio",
        help="Directory to save audio files (default: ./audio)",
    )
    parser.add_argument(
        "--format",
        default="mp3",
        help="Output audio format (default: mp3)",
    )
    return parser


def _build_overlay_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper overlay",
        description="Overlay an audio track onto a video file.",
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument(
        "--outdir",
        default="overlay",
        help="Directory to save output (default: ./overlay)",
    )
    parser.add_argument(
        "--fade",
        type=float,
        default=3.0,
        help="Fade out duration in seconds (default: 3)",
    )
    return parser


def _build_denoise_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper denoise",
        description="Reduce background noise in a video's audio.",
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument(
        "--outdir",
        default="denoised",
        help="Directory to save output (default: ./denoised)",
    )
    parser.add_argument(
        "--strength",
        type=float,
        default=0.5,
        help="Noise reduction strength 0.0-1.0 (default: 0.5, higher = more aggressive)",
    )
    return parser


def _build_captions_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videoclipper captions",
        description="Burn subtitles/captions into a video.",
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("subtitles", help="Path to subtitle file (SRT, VTT, ASS)")
    parser.add_argument(
        "--outdir",
        default="captioned",
        help="Directory to save output (default: ./captioned)",
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=24,
        help="Font size for captions (default: 24)",
    )
    parser.add_argument(
        "--position",
        choices=["bottom", "top", "center"],
        default="bottom",
        help="Position of captions (default: bottom)",
    )
    return parser


def _resolve_ranges(args: argparse.Namespace) -> list[tuple[int, int]]:
    if args.clips:
        if args.start or args.end:
            raise ClipperError("Use either --clips or start/end, not both.")
        return parse_clip_ranges(args.clips)

    if args.start is None or args.end is None:
        raise ClipperError("Start and end are required unless --clips is provided.")
    start = parse_time(args.start)
    end = parse_time(args.end)
    return [(start, end)]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "web":
        parser = _build_web_parser()
        args = parser.parse_args(argv[1:])
        print(f"Starting web server at http://{args.host}:{args.port}")
        print("Press Ctrl+C to stop")
        run_server(host=args.host, port=args.port)
        return 0

    if argv and argv[0] == "audio":
        parser = _build_audio_parser()
        args = parser.parse_args(argv[1:])
        try:
            output = download_audio(
                url=args.url,
                outdir=Path(args.outdir),
                output_format=args.format.strip().lstrip("."),
            )
        except ClipperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(output)
        return 0

    if argv and argv[0] == "overlay":
        parser = _build_overlay_parser()
        args = parser.parse_args(argv[1:])
        try:
            output = overlay_audio(
                video_path=Path(args.video),
                audio_path=Path(args.audio),
                outdir=Path(args.outdir),
                fade_duration=args.fade,
            )
        except ClipperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(output)
        return 0

    if argv and argv[0] == "denoise":
        parser = _build_denoise_parser()
        args = parser.parse_args(argv[1:])
        try:
            output = denoise_video(
                video_path=Path(args.video),
                outdir=Path(args.outdir),
                strength=args.strength,
            )
        except ClipperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(output)
        return 0

    if argv and argv[0] == "download":
        parser = _build_download_parser()
        args = parser.parse_args(argv[1:])
        try:
            output = download_url(
                url=args.url,
                outdir=Path(args.outdir),
                reencode=args.reencode,
                quality_height=args.quality_height,
            )
        except ClipperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(output)
        return 0

    if argv and argv[0] == "clip":
        parser = _build_local_clip_parser()
        args = parser.parse_args(argv[1:])
        try:
            ranges = _resolve_ranges(args)
            output_format = args.format.strip().lstrip(".")
            if not output_format:
                raise ClipperError("Output format must be a non-empty extension.")
            outputs = clip_source(
                source=Path(args.source),
                ranges=ranges,
                outdir=Path(args.outdir),
                reencode=args.reencode,
                output_format=output_format,
            )
        except ClipperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        for output in outputs:
            print(output)
        return 0

    parser = _build_clip_parser()
    args = parser.parse_args(argv)

    try:
        if args.getinfo:
            if args.start or args.end or args.clips:
                raise ClipperError("Use --getinfo without start/end or --clips.")
            info = get_info(args.url)
            title = info["title"] or "unknown"
            channel = info["channel"] or "unknown"
            video_id = info["video_id"] or "unknown"
            duration_text = info["duration_text"]
            duration_seconds = info["duration_seconds"]
            h264_heights = info["h264_heights"]
            all_heights = info["all_heights"]

            print(f"Title: {title}")
            print(f"Channel: {channel}")
            print(f"Video ID: {video_id}")
            if duration_seconds is None:
                print("Duration: unknown")
            else:
                print(f"Duration: {duration_text} ({duration_seconds}s)")
            print(
                "Available heights (H.264 MP4): "
                + (", ".join(str(h) for h in h264_heights) or "none")
            )
            print(
                "All video heights: "
                + (", ".join(str(h) for h in all_heights) or "none")
            )
            return 0

        ranges = _resolve_ranges(args)
        output_format = args.format.strip().lstrip(".")
        if not output_format:
            raise ClipperError("Output format must be a non-empty extension.")
        outputs = clip_url(
            url=args.url,
            ranges=ranges,
            outdir=Path(args.outdir),
            reencode=args.reencode,
            output_format=output_format,
            quality_height=args.quality_height,
        )
    except ClipperError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(output)
    return 0
