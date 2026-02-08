#!/usr/bin/env python3
"""Generate chapters from transcripts using LLM."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_solution.segment import initial_segments, generate_chapters_with_llm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcripts", required=True, help="Transcripts directory")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model")
    parser.add_argument("--api-key", help="API key (or use OPENAI_API_KEY env)")
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    transcripts_dir = Path(args.transcripts)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    transcript_files = list(transcripts_dir.glob("*.json"))
    
    print(f"📑 Generating chapters for {len(transcript_files)} transcript(s)...")
    
    for transcript_file in transcript_files:
        video_id = transcript_file.stem
        print(f"\n[{video_id}] Processing...")
        
        with open(transcript_file, "r", encoding="utf-8") as f:
            segments = json.load(f)
        
        # Initial segmentation
        coarse = initial_segments(segments, pause_threshold=2.0, min_segment_duration=30.0)
        print(f"  Initial segments: {len(coarse)}")
        
        # LLM chapter generation
        if api_key:
            chapters = generate_chapters_with_llm(
                coarse,
                llm_provider="openai",
                model=args.model,
                api_key=api_key
            )
        else:
            print("  ⚠️  No API key, using auto-generated titles")
            chapters = coarse
            for idx, ch in enumerate(chapters, 1):
                ch["chapter_title"] = f"段落 {idx}"
        
        # Save
        output_file = output_dir / f"{video_id}_chapters.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ Saved: {output_file}")
        print(f"  Chapters: {len(chapters)}")
    
    print(f"\n✓ All chapters generated!")


if __name__ == "__main__":
    main()
