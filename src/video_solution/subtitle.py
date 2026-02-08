"""Subtitle generation and burning module.

Supports:
- SRT/ASS subtitle generation from transcript
- Bilingual subtitle layout
- Burning subtitles into video with FFmpeg
"""
from pathlib import Path
from typing import List, Dict, Optional
import subprocess


def generate_srt(
    segments: List[Dict],
    output_path: str,
    text_field: str = "text",
    language: str = "zh"
) -> str:
    """
    Generate SRT subtitle file from segments.
    
    Args:
        segments: List of segments with 'start', 'end', and text field
        output_path: Output .srt file path
        text_field: Field name containing text ('text' or 'translated_text')
        language: Language code for metadata
    
    Returns:
        Output file path
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, 1):
            start_time = format_srt_time(seg["start"])
            end_time = format_srt_time(seg["end"])
            text = seg.get(text_field, "").strip()
            
            if not text:
                continue
            
            f.write(f"{idx}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")
    
    print(f"✓ Generated SRT: {output_path}")
    return output_path


def generate_bilingual_srt(
    segments: List[Dict],
    output_path: str,
    primary_field: str = "text",
    secondary_field: str = "translated_text",
    layout: str = "vertical"
) -> str:
    """
    Generate bilingual subtitle file.
    
    Args:
        segments: Segments with both original and translated text
        output_path: Output .srt file path
        primary_field: Primary language field name
        secondary_field: Secondary language field name
        layout: 'vertical' (line1\nline2) or 'horizontal' (line1 | line2)
    
    Returns:
        Output file path
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, 1):
            start_time = format_srt_time(seg["start"])
            end_time = format_srt_time(seg["end"])
            
            primary = seg.get(primary_field, "").strip()
            secondary = seg.get(secondary_field, "").strip()
            
            if not primary and not secondary:
                continue
            
            f.write(f"{idx}\n")
            f.write(f"{start_time} --> {end_time}\n")
            
            if layout == "vertical":
                f.write(f"{primary}\n")
                f.write(f"{secondary}\n\n")
            else:  # horizontal
                f.write(f"{primary} | {secondary}\n\n")
    
    print(f"✓ Generated bilingual SRT: {output_path}")
    return output_path


def format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def burn_subtitles(
    input_video: str,
    subtitle_file: str,
    output_path: str,
    subtitle_style: Optional[str] = None,
    force_style: Optional[str] = None
) -> str:
    """
    Burn subtitles into video using FFmpeg.
    
    Args:
        input_video: Input video file
        subtitle_file: SRT or ASS subtitle file
        output_path: Output video path
        subtitle_style: ASS style override string
        force_style: Force style parameters (for SRT)
    
    Returns:
        Output video path
    
    Example force_style:
        "FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000"
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Build subtitle filter
    if subtitle_file.endswith(".ass"):
        subtitle_filter = f"ass={subtitle_file}"
    else:  # .srt
        subtitle_filter = f"subtitles={subtitle_file}"
        
        if force_style:
            subtitle_filter += f":force_style='{force_style}'"
    
    # Escape special characters in path for FFmpeg
    subtitle_filter = subtitle_filter.replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", input_video,
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "copy",
        output_path, "-y"
    ]
    
    print(f"🔥 Burning subtitles into video...")
    subprocess.run(cmd, check=True)
    print(f"✓ Subtitled video saved: {output_path}")
    return output_path


def create_bilingual_ass(
    segments: List[Dict],
    output_path: str,
    primary_field: str = "text",
    secondary_field: str = "translated_text",
    video_width: int = 1920,
    video_height: int = 1080,
    primary_style: Optional[Dict] = None,
    secondary_style: Optional[Dict] = None
) -> str:
    """
    Create bilingual ASS subtitle with customizable styling.
    
    ASS format provides better control over positioning and styling.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Default styles
    default_primary = {
        "FontName": "Arial",
        "FontSize": 28,
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "Outline": 2,
        "MarginV": 80
    }
    
    default_secondary = {
        "FontName": "Arial",
        "FontSize": 22,
        "PrimaryColour": "&H00FFFF00",
        "OutlineColour": "&H00000000",
        "Outline": 2,
        "MarginV": 40
    }
    
    p_style = {**default_primary, **(primary_style or {})}
    s_style = {**default_secondary, **(secondary_style or {})}
    
    with open(output_path, "w", encoding="utf-8") as f:
        # Write ASS header
        f.write("[Script Info]\n")
        f.write(f"Title: Bilingual Subtitles\n")
        f.write(f"ScriptType: v4.00+\n")
        f.write(f"PlayResX: {video_width}\n")
        f.write(f"PlayResY: {video_height}\n\n")
        
        # Write styles
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        
        # Primary language style
        f.write(f"Style: Primary,{p_style['FontName']},{p_style['FontSize']},{p_style['PrimaryColour']},&H000000FF,{p_style['OutlineColour']},&H00000000,0,0,0,0,100,100,0,0,1,{p_style['Outline']},0,2,10,10,{p_style['MarginV']},1\n")
        
        # Secondary language style
        f.write(f"Style: Secondary,{s_style['FontName']},{s_style['FontSize']},{s_style['PrimaryColour']},&H000000FF,{s_style['OutlineColour']},&H00000000,0,0,0,0,100,100,0,0,1,{s_style['Outline']},0,2,10,10,{s_style['MarginV']},1\n\n")
        
        # Write events
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        for seg in segments:
            start = format_ass_time(seg["start"])
            end = format_ass_time(seg["end"])
            
            primary = seg.get(primary_field, "").strip()
            secondary = seg.get(secondary_field, "").strip()
            
            if primary:
                f.write(f"Dialogue: 0,{start},{end},Primary,,0,0,0,,{primary}\n")
            
            if secondary:
                f.write(f"Dialogue: 0,{start},{end},Secondary,,0,0,0,,{secondary}\n")
    
    print(f"✓ Generated bilingual ASS: {output_path}")
    return output_path


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format: H:MM:SS.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
