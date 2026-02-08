"""Fetch video lists from a channel and export JSON/CSV."""
from typing import List, Dict, Optional
from pathlib import Path
import json
import csv
import subprocess


def _run_yt_dlp_json(url: str, cookies: Optional[str] = None, extra_args: Optional[List[str]] = None) -> Dict:
    """Run yt-dlp and return JSON output."""
    cmd = ["yt-dlp", "-J", "--no-warnings"]
    if cookies:
        cmd.extend(["--cookies", cookies])
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ yt-dlp error: {e.stderr}")
        raise
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        raise


def fetch_channel_list(
    channel_url: str = None,
    out_path: str = "output/list.json",
    out_format: str = "json",
    cookies_path: Optional[str] = None
) -> List[Dict]:
    """Fetch video list using `yt-dlp` and write JSON or CSV manifest.

    Args:
        channel_url: YouTube channel/playlist URL. If None, raises ValueError.
        out_path: Output path for JSON/CSV.
        out_format: 'json' or 'csv'.
        cookies_path: optional path to cookies.txt (Netscape format), pass directly.

    Returns:
        list of video metadata dicts.
    """
    if not channel_url:
        raise ValueError("channel_url is required")

    print(f"📡 Fetching videos from: {channel_url}")
    info = _run_yt_dlp_json(channel_url, cookies=cookies_path)

    entries = info.get("entries") or []
    result = []

    for idx, e in enumerate(entries, 1):
        # Get video ID
        video_id = e.get("id") or e.get("url")
        if not video_id:
            continue
        
        video_url = e.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"

        # Extract basic info
        duration = e.get("duration")
        upload_date = e.get("upload_date")
        title = e.get("title")
        is_live = e.get("is_live", False)
        live_status = e.get("live_status")

        # If missing critical fields, fetch full info
        if duration is None or upload_date is None or title is None:
            try:
                print(f"  [{idx}/{len(entries)}] Fetching details for {video_id}...")
                info_v = _run_yt_dlp_json(video_url, cookies=cookies_path, extra_args=["--skip-download"])
                duration = duration or info_v.get("duration")
                upload_date = upload_date or info_v.get("upload_date")
                title = title or info_v.get("title")
                is_live = is_live or info_v.get("is_live", False)
                live_status = live_status or info_v.get("live_status")
            except Exception as e:
                print(f"  ⚠️  Failed to fetch {video_id}: {e}")
                continue

        # Determine if it's a live replay (FIXED LOGIC)
        is_live_replay = False
        if live_status == "was_live":  # 🔧 Fixed: was_live is exact string value
            is_live_replay = True
        elif is_live:  # Currently live
            is_live_replay = False

        item = {
            "video_id": video_id,
            "title": title or "Unknown",
            "duration": duration,
            "publish_date": upload_date,
            "is_live_replay": bool(is_live_replay),
            "is_live": bool(is_live),
            "live_status": live_status,
            "source_url": video_url,
        }
        result.append(item)
        
        if idx % 10 == 0:
            print(f"  Processed {idx}/{len(entries)} videos...")

    # Save output
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    if out_format == "json":
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
    else:
        csv_path = out_path if out_path.lower().endswith(".csv") else Path(out_path).with_suffix(".csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            fieldnames = ["video_id", "title", "duration", "publish_date", "is_live_replay", "is_live", "live_status", "source_url"]
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(result)

    print(f"✓ Saved {len(result)} videos to {out_path}")
    return result


def read_manifest(path: str) -> List[Dict]:
    """Load manifest JSON."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
