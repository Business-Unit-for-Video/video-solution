"""Segmentation and timeline generation.

Strategy:
- Initial automatic split by pauses, topic keywords, speaker change.
- Then send segments to LLM for chapter title generation.
- Supports: OpenAI, Anthropic, and Ollama (local/free)
"""
from typing import List, Dict, Optional
import re
import json
import requests


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


def generate_chapters_with_ollama(
    segments: List[Dict],
    model: str = "qwen2.5:14b",
    ollama_host: str = "http://localhost:11434",
    temperature: float = 0.7
) -> List[Dict]:
    """Generate chapter titles using Ollama (local LLM).

    Args:
        segments: List of segments from initial_segments()
        model: Ollama model name (qwen2.5:14b, llama3.1, etc.)
        ollama_host: Ollama server URL
        temperature: Generation temperature (0.0-1.0)

    Returns:
        Segments with added 'chapter_title' field
    """
    # Build prompt
    prompt_parts = ["根据以下转写文本和时间戳，为每个片段生成简短的章节标题（5-10个字）。\n"]
    for idx, seg in enumerate(segments, 1):
        start_time = format_timestamp(seg["start"])
        text_preview = seg["text"][:200] + ("..." if len(seg["text"]) > 200 else "")
        prompt_parts.append(f"\n片段 {idx} [{start_time}]:\n{text_preview}\n")
    
    prompt_parts.append("\n请严格按照以下 JSON 格式返回（不要添加额外说明）：")
    prompt_parts.append('\n[{"segment": 1, "title": "点评教友英文版视频"}, {"segment": 2, "title": "预测美伊冲突"}]')
    
    prompt = "".join(prompt_parts)

    try:
        print(f"🤖 Using Ollama model: {model}")
        
        # Call Ollama API
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": temperature,
                "options": {
                    "num_predict": 2000,  # Max tokens
                }
            },
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
        
        result = response.json()
        content = result.get("response", "")
        
        # Extract JSON from response
        # Try to find JSON array in the response
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        
        # Parse JSON
        titles = json.loads(content)
        
        # Apply titles to segments
        for item in titles:
            seg_idx = item["segment"] - 1
            if 0 <= seg_idx < len(segments):
                segments[seg_idx]["chapter_title"] = item["title"]
        
        print(f"✓ Generated {len(titles)} chapter titles with Ollama")
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Ollama at {ollama_host}")
        print(f"   Please start Ollama: ollama serve")
        print(f"   Or install: curl -fsSL https://ollama.com/install.sh | sh")
        # Fallback to placeholder titles
        for idx, seg in enumerate(segments, 1):
            seg["chapter_title"] = f"第 {idx} 段"
    
    except Exception as e:
        print(f"⚠️  Ollama chapter generation failed: {e}")
        # Fallback to placeholder titles
        for idx, seg in enumerate(segments, 1):
            seg["chapter_title"] = f"第 {idx} 段"

    return segments


def generate_chapters_with_llm(
    segments: List[Dict],
    llm_provider: str = "ollama",
    model: str = "qwen2.5:14b",
    api_key: Optional[str] = None,
    ollama_host: str = "http://localhost:11434"
) -> List[Dict]:
    """Generate chapter titles using LLM.

    Args:
        segments: List of segments from initial_segments()
        llm_provider: 'ollama' (default/free), 'openai', or 'anthropic'
        model: Model name
            - Ollama: 'qwen2.5:14b', 'llama3.1:70b', 'mistral', etc.
            - OpenAI: 'gpt-4o-mini', 'gpt-4o', etc.
        api_key: API key (only for openai/anthropic)
        ollama_host: Ollama server URL (default: http://localhost:11434)

    Returns:
        Segments with added 'chapter_title' field
    """
    # If no provider specified or using Ollama
    if llm_provider == "ollama" or (llm_provider == "openai" and not api_key):
        return generate_chapters_with_ollama(
            segments=segments,
            model=model,
            ollama_host=ollama_host
        )

    # OpenAI provider
    if llm_provider == "openai":
        if not api_key:
            print("⚠️  No API key provided, falling back to Ollama")
            return generate_chapters_with_ollama(segments, model="qwen2.5:14b")
        
        # Build prompt
        prompt_parts = ["根据以下转写文本和时间戳，为每个片段生成简短的章节标题（5-10个字）。\n"]
        for idx, seg in enumerate(segments, 1):
            start_time = format_timestamp(seg["start"])
            text_preview = seg["text"][:200] + ("..." if len(seg["text"]) > 200 else "")
            prompt_parts.append(f"\n片段 {idx} [{start_time}]:\n{text_preview}\n")
        
        prompt_parts.append("\n请以 JSON 格式返回，例如：")
        prompt_parts.append('[{"segment": 1, "title": "点评教友英文版视频"}, {"segment": 2, "title": "预测美伊冲突"}]')
        
        prompt = "".join(prompt_parts)

        try:
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
            
            titles = json.loads(content)
            
            for item in titles:
                seg_idx = item["segment"] - 1
                if 0 <= seg_idx < len(segments):
                    segments[seg_idx]["chapter_title"] = item["title"]
            
            print(f"✓ Generated {len(titles)} chapter titles with OpenAI")
            
        except Exception as e:
            print(f"⚠️  OpenAI chapter generation failed: {e}")
            print(f"   Falling back to Ollama...")
            return generate_chapters_with_ollama(segments, model="qwen2.5:14b")
    
    # Anthropic provider
    elif llm_provider == "anthropic":
        if not api_key:
            print("⚠️  No API key provided, falling back to Ollama")
            return generate_chapters_with_ollama(segments, model="qwen2.5:14b")
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            
            # Build prompt (similar to OpenAI)
            prompt_parts = ["根据以下转写文本和时间戳，为每个片段生成简短的章节标题（5-10个字）。\n"]
            for idx, seg in enumerate(segments, 1):
                start_time = format_timestamp(seg["start"])
                text_preview = seg["text"][:200] + ("..." if len(seg["text"]) > 200 else "")
                prompt_parts.append(f"\n片段 {idx} [{start_time}]:\n{text_preview}\n")
            
            prompt_parts.append("\n请以 JSON 格式返回。")
            prompt = "".join(prompt_parts)
            
            response = client.messages.create(
                model=model or "claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            
            titles = json.loads(content)
            
            for item in titles:
                seg_idx = item["segment"] - 1
                if 0 <= seg_idx < len(segments):
                    segments[seg_idx]["chapter_title"] = item["title"]
            
            print(f"✓ Generated {len(titles)} chapter titles with Claude")
            
        except Exception as e:
            print(f"⚠️  Anthropic chapter generation failed: {e}")
            print(f"   Falling back to Ollama...")
            return generate_chapters_with_ollama(segments, model="qwen2.5:14b")
    
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

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
