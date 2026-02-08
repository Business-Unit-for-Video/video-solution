"""Segmentation and timeline generation.

Strategy:
- Initial automatic split by pauses, topic keywords, speaker change.
- Then send segments to LLM for chapter title generation.
"""
from typing import List, Dict, Optional
import re


def initial_segments(
    transcript_segments: List[Dict],
    pause_threshold: float = 2.0,
    min_segment_duration: float = 30.0
) -> List[Dict]:
    """Create coarse segments from timestamped transcript.

    Args:
        transcript_segments: List from ASR with start/end/text/speaker
        pause_threshold: Max gap (seconds) within a segment
        min_segment_duration: Minimum segment duration (seconds)

    Returns:
        List of merged segments: [{"start": float, "end": float, "text": str, "speaker": str}]
    """
    if not transcript_segments:
        return []

    merged = []
    current = transcript_segments[0].copy()

    for seg in transcript_segments[1:]:
        gap = seg["start"] - current["end"]
        speaker_changed = seg.get("speaker") != current.get("speaker")
        
        # Merge if gap is small and same speaker
        if gap <= pause_threshold and not speaker_changed:
            current["end"] = seg["end"]
            current["text"] += " " + seg["text"]
        else:
            # Start new segment if gap is large OR speaker changed
            if current["end"] - current["start"] >= min_segment_duration:
                merged.append(current)
            current = seg.copy()

    # Add last segment
    if current["end"] - current["start"] >= min_segment_duration:
        merged.append(current)

    return merged


def generate_chapters_with_llm(
    segments: List[Dict],
    llm_provider: str = "openai",
    model: str = "gpt-4o",
    api_key: Optional[str] = None
) -> List[Dict]:
    """Generate chapter titles using LLM.

    Args:
        segments: List of segments from initial_segments()
        llm_provider: 'openai' or 'anthropic'
        model: Model name
        api_key: API key for the provider

    Returns:
        Segments with added 'chapter_title' field
    """
    if not api_key:
        print("⚠️  No API key provided, using placeholder titles")
        for idx, seg in enumerate(segments, 1):
            seg["chapter_title"] = f"第 {idx} 段"
        return segments

    # Build prompt
    prompt_parts = ["根据以下转写文本和时间戳，为每个片段生成简短的章节标题（5-10个字）。\n"]
    for idx, seg in enumerate(segments, 1):
        start_time = format_timestamp(seg["start"])
        text_preview = seg["text"][:200] + ("..." if len(seg["text"]) > 200 else "")
        prompt_parts.append(f"\n片段 {idx} [{start_time}]:\n{text_preview}\n")
    
    prompt_parts.append("\n请以 JSON 格式返回，例如：")
    prompt_parts.append('[{"segment": 1, "title": "点评教友英文版视频"}, {"segment": 2, "title": "预测美伊冲突"}]')
    
    prompt = "".join(prompt_parts)

    # Call LLM
    try:
        if llm_provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个视频章节生成助手，擅长从转写文本中提取主题并生成简洁的标题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content
            
            # Extract JSON from markdown code block if present
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            import json
            titles = json.loads(content)
            
            for item in titles:
                seg_idx = item["segment"] - 1
                if 0 <= seg_idx < len(segments):
                    segments[seg_idx]["chapter_title"] = item["title"]
            
            print(f"✓ Generated {len(titles)} chapter titles")
            
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")
            
    except Exception as e:
        print(f"⚠️  LLM chapter generation failed: {e}")
        for idx, seg in enumerate(segments, 1):
            seg["chapter_title"] = f"第 {idx} 段"

    return segments


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_chapters_youtube(segments: List[Dict]) -> str:
    """Format chapters for YouTube description.

    Example output:
    00:00 开场
    01:37 点评教友英文版视频
    07:36 预测美伊冲突
    """
    lines = []
    for seg in segments:
        timestamp = format_timestamp(seg["start"])
        title = seg.get("chapter_title", "未命名")
        lines.append(f"{timestamp} {title}")
    return "\n".join(lines)
