"""Test script for downloader.download_audio.

Usage:
    python scripts/test_download.py --url <VIDEO_URL> [--out output/audio] [--cookies cookies.txt]
"""
import argparse
from pathlib import Path
from video_solution.downloader import download_audio


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--out", default="output/audio")
    p.add_argument("--cookies", default=None)
    p.add_argument("--format", default="m4a")
    args = p.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    files = download_audio(args.url, out_dir=args.out, cookies_path=args.cookies, format_ext=args.format, quiet=False)
    print("Downloaded:")
    for f in files:
        print(f)


if __name__ == "__main__":
    main()
