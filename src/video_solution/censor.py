"""Censorship utilities: map transcript matches to time ranges and mute/beep audio.

Approach:
- Find sensitive tokens in transcript -> map to segments -> apply silence or beep over audio tracks
  using ffmpeg filters for exact time ranges.
"""
from typing import List, Dict
import subprocess
from pathlib import Path


def _get_channel_count(input_audio: str) -> int:
    """Return number of audio channels using ffprobe. Defaults to 2 on failure."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=channels",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_audio,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        out = proc.stdout.strip()
        return int(out) if out.isdigit() else 2
    except Exception:
        return 2


def apply_audio_censor(
    input_audio: str,
    ranges: List[Dict],
    mode: str = "beep",
    out_audio: str = "output/censored.m4a",
    default_freq: int = 1000,
    default_waveform: str = "sine",
    default_amp: float = 0.8
) -> str:
    """Apply censorship over time ranges. `ranges` is list of {start, end}.
    
    Each range can optionally contain `freq`, `waveform`, and `amp` keys to control the beep.

    Args:
        input_audio: Input audio file path
        ranges: List of dicts with 'start' and 'end' keys (in seconds)
        mode: 'beep' or 'mute'
        out_audio: Output audio file path
        default_freq: Default beep frequency (Hz)
        default_waveform: Default waveform type ('sine', 'square', 'triangle', 'sawtooth')
        default_amp: Default beep amplitude (0.0-1.0)

    Returns:
        Path to output audio file
    """
    Path(out_audio).parent.mkdir(parents=True, exist_ok=True)

    if not ranges:
        # Nothing to censor, copy input to output
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", input_audio,
            "-c", "copy",
            out_audio, "-y",
        ]
        subprocess.run(cmd, check=True)
        return out_audio

    # Build enable expression: between(t,start,end) for each range
    expr_parts = [f"between(t,{float(r['start'])},{float(r['end'])})" for r in ranges]
    enable_expr = "||".join(expr_parts)

    if mode == "mute":
        # Apply volume filter that mutes when expression is true
        afilter = f"volume=enable='{enable_expr}':volume=0"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", input_audio,
            "-af", afilter,
            "-c:a", "aac",
            out_audio, "-y",
        ]
        subprocess.run(cmd, check=True)
        return out_audio

    if mode == "beep":
        channel_count = _get_channel_count(input_audio)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", input_audio]

        # Generate beep for each range
        for r in ranges:
            start = float(r.get("start", 0.0))
            end = float(r.get("end", start + 0.5))
            duration = max(0.1, end - start)
            freq = int(r.get("freq", default_freq))
            waveform = r.get("waveform", default_waveform)
            amp = float(r.get("amp", default_amp))

            # Generate sine wave (or other waveforms if supported)
            lavfi = f"sine=frequency={freq}:sample_rate=44100:duration={duration}"
            cmd += ["-f", "lavfi", "-i", lavfi]

        # Build filter_complex
        filters = []
        
        # Mute original in ranges
        filters.append(f"[0:a]volume=enable='{enable_expr}':volume=0[clean]")

        # Process each beep: apply volume and delay
        sine_labels = []
        for idx, r in enumerate(ranges, start=1):
            start_ms = int(float(r.get("start", 0.0)) * 1000)
            amp = float(r.get("amp", default_amp))
            delay_vals = "|".join([str(start_ms)] * channel_count)
            
            filters.append(f"[{idx}:a]volume={amp},adelay={delay_vals}[s{idx}]")
            sine_labels.append(f"[s{idx}]")

        # Mix clean audio + all beeps
        mix_inputs = 1 + len(ranges)
        inputs_labels = "".join(["[clean]"] + sine_labels)
        filters.append(f"{inputs_labels}amix=inputs={mix_inputs}:dropout_transition=0:normalize=0[outa]")

        filter_complex = ";".join(filters)
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[outa]",
            "-c:a", "aac",
            out_audio, "-y"
        ]

        subprocess.run(cmd, check=True)
        return out_audio

    raise ValueError(f"Unsupported mode: {mode}")
