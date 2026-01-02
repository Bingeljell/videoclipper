from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clipper import ClipperError, clip_url, parse_clip_ranges, parse_time


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtubeclipper",
        description="Download a YouTube video and generate one or more clips.",
    )
    parser.add_argument("url", help="YouTube video URL")
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
    parser.add_argument(
        "--format",
        default="mp4",
        help="Output container extension (default: mp4)",
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
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
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
