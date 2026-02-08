#!/usr/bin/env python3
"""Generate HTML report from artifacts."""
import argparse
import json
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    
    artifacts_dir = Path(args.artifacts_dir)
    
    # Collect statistics
    stats = {
        "generated_at": datetime.now().isoformat(),
        "videos": 0,
        "transcripts": 0,
        "chapters": 0,
    }
    
    # Count videos
    video_list = artifacts_dir / "video-list" / "list.json"
    if video_list.exists():
        with open(video_list, "r") as f:
            stats["videos"] = len(json.load(f))
    
    # Count transcripts
    transcripts_dir = artifacts_dir / "transcripts"
    if transcripts_dir.exists():
        stats["transcripts"] = len(list(transcripts_dir.glob("*.json")))
    
    # Count chapters
    chapters_dir = artifacts_dir / "chapters"
    if chapters_dir.exists():
        stats["chapters"] = len(list(chapters_dir.glob("*.json")))
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Processing Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; }}
            h1 {{ color: #333; }}
            .stat {{ background: #f0f0f0; padding: 20px; margin: 10px 0; border-radius: 5px; }}
            .stat h3 {{ margin: 0 0 10px 0; }}
            .stat p {{ margin: 0; font-size: 24px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🎬 Video Processing Report</h1>
        <p>Generated: {stats['generated_at']}</p>
        
        <div class="stat">
            <h3>📥 Videos Fetched</h3>
            <p>{stats['videos']}</p>
        </div>
        
        <div class="stat">
            <h3>🎤 Transcripts Generated</h3>
            <p>{stats['transcripts']}</p>
        </div>
        
        <div class="stat">
            <h3>📑 Chapters Created</h3>
            <p>{stats['chapters']}</p>
        </div>
    </body>
    </html>
    """
    
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        f.write(html)
    
    print(f"✓ Report generated: {args.out}")


if __name__ == "__main__":
    main()
