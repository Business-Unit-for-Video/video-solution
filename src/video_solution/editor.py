"""Editor utilities: cut video/audio aligned to keyframes and write metadata."""
from pathlib import Path
import subprocess
import json
from typing import List, Dict, Optional, Tuple


def find_keyframes(video_path: str, output_json: Optional[str] = None) -> List[float]:
    """
    Find all keyframe timestamps in a video using ffprobe.
    
    Args:
        video_path: Input video file
        output_json: Optional path to save keyframe list
    
    Returns:
        List of keyframe timestamps (in seconds)
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "frame=pkt_pts_time,pict_type",
        "-of", "json",
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    
    keyframes = []
    for frame in data.get("frames", []):
        if frame.get("pict_type") == "I":  # I-frame = keyframe
            timestamp = float(frame.get("pkt_pts_time", 0))
            keyframes.append(timestamp)
    
    if output_json:
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w") as f:
            json.dump({"keyframes": keyframes, "count": len(keyframes)}, f, indent=2)
    
    print(f"✓ Found {len(keyframes)} keyframes")
    return keyframes


def find_nearest_keyframe(target_time: float, keyframes: List[float], direction: str = "before") -> float:
    """
    Find nearest keyframe to target time.
    
    Args:
        target_time: Target timestamp (seconds)
        keyframes: List of keyframe timestamps
        direction: 'before' or 'after'
    
    Returns:
        Nearest keyframe timestamp
    """
    if not keyframes:
        return target_time
    
    if direction == "before":
        valid = [kf for kf in keyframes if kf <= target_time]
        return max(valid) if valid else keyframes[0]
    else:  # after
        valid = [kf for kf in keyframes if kf >= target_time]
        return min(valid) if valid else keyframes[-1]


def cut_segment(
    input_path: str,
    start: float,
    end: float,
    out_path: str,
    keyframes: Optional[List[float]] = None,
    align_keyframes: bool = True,
    metadata: Optional[Dict] = None
) -> Tuple[str, Dict]:
    """
    Cut a segment from video/audio, optionally aligning to keyframes.
    
    Args:
        input_path: Input video/audio file
        start: Start time (seconds)
        end: End time (seconds)
        out_path: Output file path
        keyframes: Pre-computed keyframe list (optional, will compute if None)
        align_keyframes: Whether to align cuts to keyframes
        metadata: Optional metadata to embed (dict)
    
    Returns:
        Tuple of (output_path, actual_cut_metadata)
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    actual_start = start
    actual_end = end
    
    # Align to keyframes if requested
    if align_keyframes and input_path.endswith((".mp4", ".mkv", ".avi", ".mov")):
        if keyframes is None:
            print(f"  Computing keyframes for: {Path(input_path).name}")
            keyframes = find_keyframes(input_path)
        
        actual_start = find_nearest_keyframe(start, keyframes, "before")
        actual_end = find_nearest_keyframe(end, keyframes, "after")
        
        drift = abs(actual_start - start) + abs(actual_end - end)
        if drift > 1.0:
            print(f"  ⚠️  Keyframe drift: {drift:.2f}s")
    
    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(actual_start),
        "-to", str(actual_end),
        "-i", input_path,
    ]
    
    # Try stream copy for faster processing (only works with keyframe alignment)
    if align_keyframes and abs(actual_start - start) < 0.1:
        cmd.extend(["-c", "copy"])
    else:
        # Re-encode for precise cuts
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac"])
    
    # Add metadata if provided
    if metadata:
        for key, value in metadata.items():
            cmd.extend(["-metadata", f"{key}={value}"])
    
    cmd.extend([out_path, "-y"])
    
    subprocess.run(cmd, check=True)
    
    cut_metadata = {
        "requested_start": start,
        "requested_end": end,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "duration": actual_end - actual_start
    }
    
    return out_path, cut_metadata


def batch_cut_segments(
    input_video: str,
    segments: List[Dict],
    output_dir: str = "output/segments",
    align_keyframes: bool = True
) -> List[Dict]:
    """
    Cut multiple segments from a video.
    
    Args:
        input_video: Input video file
        segments: List of segments with 'start', 'end', 'chapter_title'
        output_dir: Output directory for segments
        align_keyframes: Whether to align to keyframes
    
    Returns:
        Segments with added 'video_path' and 'cut_metadata' fields
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Pre-compute keyframes once
    keyframes = find_keyframes(input_video) if align_keyframes else None
    
    print(f"✂️  Cutting {len(segments)} segments...")
    
    for idx, seg in enumerate(segments):
        filename = f"segment_{idx:04d}_{safe_filename(seg.get('chapter_title', 'untitled'))}.mp4"
        out_file = output_path / filename
        
        metadata = {
            "title": seg.get("chapter_title", f"Segment {idx+1}"),
            "segment_id": str(idx),
            "start_time": str(seg["start"]),
            "end_time": str(seg["end"])
        }
        
        try:
            video_path, cut_meta = cut_segment(
                input_path=input_video,
                start=seg["start"],
                end=seg["end"],
                out_path=str(out_file),
                keyframes=keyframes,
                align_keyframes=align_keyframes,
                metadata=metadata
            )
            
            seg["video_path"] = video_path
            seg["cut_metadata"] = cut_meta
            print(f"  ✓ [{idx+1}/{len(segments)}] {filename}")
            
        except Exception as e:
            print(f"  ❌ Failed segment {idx}: {e}")
            seg["video_path"] = None
            seg["cut_metadata"] = None
    
    return segments


def safe_filename(text: str, max_length: int = 50) -> str:
    """Convert text to safe filename."""
    import re
    # Remove invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '', text)
    # Replace spaces with underscores
    safe = safe.replace(' ', '_')
    # Limit length
    return safe[:max_length]


def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    video_offset: float = 0.0
) -> str:
    """
    Replace video's audio track with new audio.
    
    Args:
        video_path: Input video file
        audio_path: New audio file
        output_path: Output file path
        video_offset: Offset to sync video (seconds)
    
    Returns:
        Output file path
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", video_path,
    ]
    
    if video_offset != 0:
        cmd.extend(["-itsoffset", str(video_offset)])
    
    cmd.extend([
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",  # End when shortest stream ends
        output_path, "-y"
    ])
    
    subprocess.run(cmd, check=True)
    return output_path
