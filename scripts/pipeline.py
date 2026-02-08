#!/usr/bin/env python3
"""
Complete video processing pipeline.

Usage:
    python scripts/pipeline.py --channel-url "https://youtube.com/@channel" --cookies cookies.txt
"""
import argparse
from pathlib import Path
import json
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_solution.fetch_list import fetch_channel_list
from src.video_solution.downloader import download_audio
from src.video_solution.asr import transcribe_and_align
from src.video_solution.segment import initial_segments, generate_chapters_with_llm
from src.video_solution.editor import batch_cut_segments
from src.video_solution.translate_tts import translate_with_timing, GPTSoVITSCloner, generate_dubbed_audio


def main():
    parser = argparse.ArgumentParser(description="Complete video processing pipeline")
    parser.add_argument("--channel-url", required=True, help="YouTube channel/playlist URL")
    parser.add_argument("--cookies", required=True, help="Path to cookies.txt")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--limit", type=int, default=1, help="Max videos to process")
    parser.add_argument("--openai-key", help="OpenAI API key for chapters/translation")
    parser.add_argument("--hf-token", help="HuggingFace token for diarization")
    parser.add_argument("--target-lang", default="en", choices=["en", "zh", "ja", "es"])
    parser.add_argument("--skip-translation", action="store_true", help="Skip translation step")
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Fetch video list
    print("\n" + "="*60)
    print("STEP 1: Fetching video list")
    print("="*60)
    manifest_path = output_dir / "list.json"
    videos = fetch_channel_list(
        channel_url=args.channel_url,
        out_path=str(manifest_path),
        cookies_path=args.cookies
    )
    
    if args.limit > 0:
        videos = videos[:args.limit]
    
    print(f"\n✓ Processing {len(videos)} video(s)")
    
    # Process each video
    for idx, video in enumerate(videos, 1):
        video_id = video["video_id"]
        print(f"\n{'='*60}")
        print(f"Processing video {idx}/{len(videos)}: {video['title'][:50]}")
        print(f"Video ID: {video_id}")
        print(f"{'='*60}")
        
        video_dir = output_dir / video_id
        video_dir.mkdir(exist_ok=True)
        
        # Step 2: Download audio
        print("\nSTEP 2: Downloading audio...")
        audio_files = download_audio(
            url=video["source_url"],
            out_dir=str(video_dir / "audio"),
            cookies_path=args.cookies
        )
        
        if not audio_files:
            print(f"❌ Failed to download audio for {video_id}")
            continue
        
        audio_path = audio_files[0]
        print(f"✓ Audio saved: {audio_path}")
        
        # Step 3: Transcribe
        print("\nSTEP 3: Transcribing...")
        transcript_path = video_dir / "transcript.json"
        segments = transcribe_and_align(
            audio_path=audio_path,
            hf_token=args.hf_token,
            output_json=str(transcript_path)
        )
        
        # Step 4: Generate chapters
        print("\nSTEP 4: Generating chapters...")
        coarse_segments = initial_segments(segments, pause_threshold=2.0)
        
        if args.openai_key:
            chapters = generate_chapters_with_llm(
                coarse_segments,
                api_key=args.openai_key
            )
        else:
            chapters = coarse_segments
            for i, ch in enumerate(chapters, 1):
                ch["chapter_title"] = f"段落 {i}"
        
        chapters_path = video_dir / "chapters.json"
        with open(chapters_path, "w", encoding="utf-8") as f:
            json.dump(chapters, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Generated {len(chapters)} chapters")
        
        # Step 5: Translation (optional)
        if not args.skip_translation and args.openai_key:
            print(f"\nSTEP 5: Translating to {args.target_lang}...")
            chapters = translate_with_timing(
                chapters,
                tgt_lang=args.target_lang,
                api_key=args.openai_key
            )
        
        # Save final result
        result_path = video_dir / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_info": video,
                "chapters": chapters,
                "stats": {
                    "total_duration": video.get("duration"),
                    "num_segments": len(segments),
                    "num_chapters": len(chapters)
                }
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ Video {idx} complete! Results saved to: {video_dir}")
    
    print(f"\n{'='*60}")
    print(f"✓ Pipeline complete! Processed {len(videos)} video(s)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
