"""ASR / transcription and alignment helpers.

This module runs WhisperX for fast ASR with word-level timestamps and speaker diarization.
"""
from typing import List, Dict, Optional
from pathlib import Path
import json


def transcribe_and_align(
    audio_path: str,
    model_name: str = "large-v2",
    device: str = "cuda",
    compute_type: str = "float16",
    batch_size: int = 16,
    language: str = None,
    enable_diarization: bool = True,
    hf_token: Optional[str] = None,
    output_json: Optional[str] = None
) -> List[Dict]:
    """Transcribe audio using WhisperX and return segments with start/end/text/speaker.

    Args:
        audio_path: Path to audio file
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3')
        device: 'cuda' or 'cpu'
        compute_type: 'float16' or 'int8' (for lower memory)
        batch_size: Batch size for processing (reduce if OOM)
        language: Language code ('zh', 'en', etc.) or None for auto-detect
        enable_diarization: Whether to enable speaker diarization
        hf_token: HuggingFace token for diarization model (required if enable_diarization=True)
        output_json: Optional path to save raw WhisperX output

    Returns:
        List of segments: [{"start": float, "end": float, "text": str, "speaker": str, "words": list}]
    """
    try:
        import whisperx
        import gc
    except ImportError:
        raise ImportError(
            "whisperx not installed. Install with: pip install whisperx"
        )

    # 1. Load audio
    audio = whisperx.load_audio(audio_path)

    # 2. Transcribe with Whisper
    print(f"🎤 Transcribing with {model_name}...")
    model = whisperx.load_model(
        model_name,
        device=device,
        compute_type=compute_type,
        language=language
    )
    result = model.transcribe(audio, batch_size=batch_size)
    
    detected_language = result.get("language", language or "unknown")
    print(f"✓ Detected language: {detected_language}")

    # Free memory
    del model
    gc.collect()
    if device == "cuda":
        import torch
        torch.cuda.empty_cache()

    # 3. Align whisper output to get word-level timestamps
    print("⏱️  Aligning timestamps...")
    align_model, metadata = whisperx.load_align_model(
        language_code=detected_language,
        device=device
    )
    result = whisperx.align(
        result["segments"],
        align_model,
        metadata,
        audio,
        device,
        return_char_alignments=False
    )

    # Free memory
    del align_model
    gc.collect()
    if device == "cuda":
        import torch
        torch.cuda.empty_cache()

    # 4. Speaker diarization (optional)
    if enable_diarization:
        if not hf_token:
            print("⚠️  Warning: HF token not provided, skipping diarization. Get token from https://huggingface.co/settings/tokens")
        else:
            try:
                print("👥 Diarizing speakers...")
                diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=hf_token,
                    device=device
                )
                diarize_segments = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                print("✓ Speaker diarization completed")
            except Exception as e:
                print(f"⚠️  Diarization failed: {e}")

    # 5. Format output
    segments = result.get("segments", [])
    formatted_segments = []
    
    for seg in segments:
        formatted_seg = {
            "start": seg.get("start", 0.0),
            "end": seg.get("end", 0.0),
            "text": seg.get("text", "").strip(),
            "speaker": seg.get("speaker", None),
            "words": seg.get("words", [])
        }
        formatted_segments.append(formatted_seg)

    # 6. Save to JSON if requested
    if output_json:
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(formatted_segments, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved transcript to {output_json}")

    print(f"✓ Transcription complete: {len(formatted_segments)} segments")
    return formatted_segments


def load_transcript(json_path: str) -> List[Dict]:
    """Load previously saved transcript JSON."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)
