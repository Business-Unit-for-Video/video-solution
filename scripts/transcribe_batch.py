#!/usr/bin/env python3
"""Batch transcribe audio files."""
import argparse
import json
import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_solution.asr import transcribe_and_align


def main():
    parser = argparse.ArgumentParser(description="Batch transcribe audio files")
    parser.add_argument("--manifest", required=True, help="Video list JSON")
    parser.add_argument("--audio-dir", required=True, help="Audio directory")
    parser.add_argument("--out", required=True, help="Output directory for transcripts")
    parser.add_argument("--model", default="large-v2", help="Whisper model size")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--language", default=None, help="Language code (auto-detect if None)")
    parser.add_argument("--hf-token", default=None, help="HuggingFace token for diarization")
    parser.add_argument("--limit", type=int, default=0, help="Max videos (0=all)")
    args = parser.parse_args()
    
    # Get HF token from env if not provided
    hf_token = args.hf_token or os.getenv("HF_TOKEN")
    
    # Load manifest
    with open(args.manifest, "r", encoding="utf-8") as f:
        videos = json.load(f)
    
    if args.limit > 0:
        videos = videos[:args.limit]
    
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🎤 Transcribing {len(videos)} video(s)...")
    print(f"   Model: {args.model}")
    print(f"   Device: {args.device}")
    
    for idx, video in enumerate(videos, 1):
        video_id = video["video_id"]
        title = video["title"][:50]
        
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(videos)}] {title}")
        print(f"{'='*60}")
        
        # Find audio file
        audio_dir = Path(args.audio_dir) / video_id
        audio_files = list(audio_dir.glob("*.*"))
        
        if not audio_files:
            print(f"  ❌ No audio found in: {audio_dir}")
            continue
        
        audio_path = str(audio_files[0])
        output_json = output_dir / f"{video_id}.json"
        
        try:
            segments = transcribe_and_align(
                audio_path=audio_path,
                model_name=args.model,
                device=args.device,
                language=args.language,
                enable_diarization=bool(hf_token),
                hf_token=hf_token,
                output_json=str(output_json)
            )
            
            print(f"  ✓ Saved: {output_json}")
            print(f"  Segments: {len(segments)}")
            
        except Exception as e:
            print(f"  ❌ Transcription failed: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"✓ Batch transcription complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
