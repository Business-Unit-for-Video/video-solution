#!/usr/bin/env python3
"""Batch download audio from video manifest."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_solution.downloader import download_audio


def main():
    parser = argparse.ArgumentParser(description="Batch download audio files")
    parser.add_argument("--manifest", required=True, help="Video list JSON from fetch-list")
    parser.add_argument("--limit", type=int, default=0, help="Max videos to download (0=all)")
    parser.add_argument("--cookies", required=True, help="Path to cookies.txt")
    parser.add_argument("--out", default="output/audio", help="Output directory")
    parser.add_argument("--format", default="m4a", choices=["mp3", "m4a", "wav"], help="Audio format")
    args = parser.parse_args()
    
    # Load manifest
    with open(args.manifest, "r", encoding="utf-8") as f:
        videos = json.load(f)
    
    if args.limit > 0:
        videos = videos[:args.limit]
    
    print(f"📥 Downloading audio for {len(videos)} video(s)...")
    
    success = 0
    failed = 0
    
    for idx, video in enumerate(videos, 1):
        video_id = video["video_id"]
        title = video["title"][:50]
        
        print(f"\n[{idx}/{len(videos)}] {title}")
        print(f"  Video ID: {video_id}")
        
        try:
            audio_files = download_audio(
                url=video["source_url"],
                out_dir=f"{args.out}/{video_id}",
                cookies_path=args.cookies,
                format_ext=args.format,
                quiet=False
            )
            
            if audio_files:
                print(f"  ✓ Downloaded: {audio_files[0]}")
                success += 1
            else:
                print(f"  ❌ No audio files returned")
                failed += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"✓ Success: {success} | ❌ Failed: {failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
