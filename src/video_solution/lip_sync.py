"""Lip sync module using Wav2Lip for video dubbing.

Wav2Lip: https://github.com/Rudrabha/Wav2Lip
"""
from pathlib import Path
from typing import Optional
import subprocess
import sys


class Wav2LipSync:
    """Wrapper for Wav2Lip lip-sync generation."""
    
    def __init__(self, wav2lip_path: str = "Wav2Lip", checkpoint: str = "checkpoints/wav2lip_gan.pth"):
        """
        Args:
            wav2lip_path: Path to Wav2Lip installation directory
            checkpoint: Path to model checkpoint (wav2lip.pth or wav2lip_gan.pth)
        """
        self.wav2lip_path = Path(wav2lip_path)
        self.checkpoint = checkpoint
        
        if not self.wav2lip_path.exists():
            raise FileNotFoundError(
                f"Wav2Lip not found at {wav2lip_path}.\n"
                f"Install: git clone https://github.com/Rudrabha/Wav2Lip.git"
            )
        
        checkpoint_full = self.wav2lip_path / checkpoint
        if not checkpoint_full.exists():
            print(f"⚠️  Checkpoint not found: {checkpoint_full}")
            print(f"   Download from: https://github.com/Rudrabha/Wav2Lip#getting-the-weights")
    
    def sync_video(
        self,
        input_video: str,
        input_audio: str,
        output_path: str,
        face_detect: str = "s3fd",
        pads: str = "0 10 0 0",
        resize_factor: int = 1,
        nosmooth: bool = False,
        box: Optional[str] = None
    ) -> str:
        """
        Generate lip-synced video using Wav2Lip.
        
        Args:
            input_video: Input video file (face should be visible)
            input_audio: New audio file to sync with
            output_path: Output video path
            face_detect: Face detection method ('s3fd' recommended)
            pads: Face padding (top bottom left right)
            resize_factor: Reduce resolution for faster processing (1=original, 2=half)
            nosmooth: Disable face smoothing
            box: Face bounding box as "x1,y1,x2,y2" (optional, auto-detect if None)
        
        Returns:
            Output video path
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Build command
        inference_script = self.wav2lip_path / "inference.py"
        
        cmd = [
            sys.executable,  # Use current Python interpreter
            str(inference_script),
            "--checkpoint_path", str(self.wav2lip_path / self.checkpoint),
            "--face", input_video,
            "--audio", input_audio,
            "--outfile", output_path,
            "--face_det_batch_size", "8",
            "--wav2lip_batch_size", "128",
            "--resize_factor", str(resize_factor),
            "--pads", pads
        ]
        
        if nosmooth:
            cmd.append("--nosmooth")
        
        if box:
            cmd.extend(["--box", box])
        
        # Change to Wav2Lip directory (required for relative imports)
        print(f"🎭 Running Wav2Lip...")
        print(f"   Video: {Path(input_video).name}")
        print(f"   Audio: {Path(input_audio).name}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.wav2lip_path),
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✓ Lip-synced video saved: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Wav2Lip failed:")
            print(e.stderr)
            raise
    
    def batch_sync_segments(
        self,
        segments: list,
        video_dir: str,
        audio_dir: str,
        output_dir: str = "output/synced"
    ) -> list:
        """
        Batch process multiple segments.
        
        Args:
            segments: List of segment dicts with 'video_path' and 'dubbed_audio_path'
            video_dir: Directory containing original video segments
            audio_dir: Directory containing dubbed audio
            output_dir: Output directory for synced videos
        
        Returns:
            Updated segments with 'synced_video_path' field
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for idx, seg in enumerate(segments):
            video_file = seg.get("video_path")
            audio_file = seg.get("dubbed_audio_path")
            
            if not video_file or not audio_file:
                print(f"  ⚠️  Skipping segment {idx}: missing video or audio")
                continue
            
            output_file = output_path / f"synced_{Path(video_file).stem}.mp4"
            
            try:
                synced = self.sync_video(
                    input_video=video_file,
                    input_audio=audio_file,
                    output_path=str(output_file)
                )
                seg["synced_video_path"] = synced
                print(f"  ✓ [{idx+1}/{len(segments)}] {output_file.name}")
                
            except Exception as e:
                print(f"  ❌ Failed segment {idx}: {e}")
                seg["synced_video_path"] = None
        
        return segments


def install_wav2lip():
    """Helper to download and setup Wav2Lip."""
    print("📥 Installing Wav2Lip...")
    
    cmds = [
        "git clone https://github.com/Rudrabha/Wav2Lip.git",
        "cd Wav2Lip && pip install -r requirements.txt",
    ]
    
    print("\nRun these commands:")
    for cmd in cmds:
        print(f"  {cmd}")
    
    print("\n📥 Download model checkpoints:")
    print("  1. wav2lip.pth (basic): https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/Eb3LEzbfuKlJiR600lQWRxgBIY27JZg80f7V9jtMfbNDaQ")
    print("  2. wav2lip_gan.pth (better quality): https://iiitaphyd-my.sharepoint.com/:u:/g/personal/radrabha_m_research_iiit_ac_in/EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA")
    print("\n📁 Place checkpoints in: Wav2Lip/checkpoints/")
