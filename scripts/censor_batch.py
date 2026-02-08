#!/usr/bin/env python3
"""Batch apply censorship to audio files."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_solution.sensitive_filter import SensitiveWordFilter
from src.video_solution.censor import apply_audio_censor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--transcripts", required=True)
    parser.add_argument("--wordlist", required=True)
    parser.add_argument("--mode", choices=["mute", "beep"], default="beep")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    
    # Load sensitive word filter
    word_filter = SensitiveWordFilter(args.wordlist)
    
    transcripts_dir = Path(args.transcripts)
    audio_dir = Path(args.audio_dir)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    transcript_files = list(transcripts_dir.glob("*.json"))
    
    print(f"🚫 Censoring {len(transcript_files)} audio file(s)...")
    
    for transcript_file in transcript_files:
        video_id = transcript_file.stem
        print(f"\n[{video_id}] Processing...")
        
        # Load transcript
        with open(transcript_file, "r") as f:
            segments = json.load(f)
        
        # Find sensitive words
        censor_ranges = word_filter.map_to_timestamps(segments)
        
        if not censor_ranges:
            print(f"  ✓ No sensitive words found")
            continue
        
        print(f"  Found {len(censor_ranges)} sensitive word(s)")
        
        # Find audio file
        audio_files = list((audio_dir / video_id).glob("*.*"))
        if not audio_files:
            print(f"  ❌ No audio file found")
            continue
        
        audio_file = audio_files[0]
        output_file = output_dir / video_id / audio_file.name
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Apply censorship
        apply_audio_censor(
            input_audio=str(audio_file),
            ranges=censor_ranges,
            mode=args.mode,
            out_audio=str(output_file)
        )
        
        print(f"  ✓ Saved: {output_file}")
    
    print(f"\n✓ Censorship complete!")


if __name__ == "__main__":
    main()
