"""Translation and TTS orchestration with voice cloning support.

Supports:
- GPT-SoVITS (recommended for best quality)
- Coqui TTS XTTS-v2
- Translation with duration constraints
"""
from typing import List, Dict, Optional
from pathlib import Path
import subprocess
import json
import time


class VoiceCloner:
    """Base class for voice cloning backends."""
    
    def train(self, audio_files: List[str], output_model_dir: str) -> str:
        """Train voice model from audio files. Returns model path."""
        raise NotImplementedError
    
    def synthesize(self, text: str, output_path: str, target_duration: Optional[float] = None) -> str:
        """Synthesize speech with optional duration constraint."""
        raise NotImplementedError


class GPTSoVITSCloner(VoiceCloner):
    """GPT-SoVITS voice cloning (1 min audio can train good TTS)."""
    
    def __init__(self, sovits_path: str = "GPT_SoVITS", device: str = "cuda"):
        """
        Args:
            sovits_path: Path to GPT-SoVITS installation directory
            device: 'cuda' or 'cpu'
        """
        self.sovits_path = Path(sovits_path)
        self.device = device
        self.reference_audio = None
        self.reference_text = None
        
        if not self.sovits_path.exists():
            raise FileNotFoundError(
                f"GPT-SoVITS not found at {sovits_path}. "
                f"Clone from: https://github.com/RVC-Boss/GPT-SoVITS"
            )
    
    def train(self, audio_files: List[str], output_model_dir: str) -> str:
        """
        Train GPT-SoVITS model. Steps:
        1. Audio slicing (slice audio into short clips)
        2. Denoising (denoise audio)
        3. ASR (transcribe audio)
        4. Fine-tuning (train model)
        
        For detailed steps, see: https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/en/README.md
        """
        output_dir = Path(output_model_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎤 Training GPT-SoVITS with {len(audio_files)} audio files...")
        print(f"⚠️  Note: This is a simplified training flow. For best results:")
        print(f"   1. Use GPT-SoVITS WebUI for interactive training")
        print(f"   2. Manually clean and denoise audio")
        print(f"   3. Verify ASR transcriptions")
        
        # Step 1: Prepare audio directory
        training_audio_dir = output_dir / "raw_audio"
        training_audio_dir.mkdir(exist_ok=True)
        
        for idx, audio_file in enumerate(audio_files):
            import shutil
            target = training_audio_dir / f"audio_{idx:03d}{Path(audio_file).suffix}"
            shutil.copy(audio_file, target)
            print(f"  Copied: {audio_file} -> {target}")
        
        print(f"\n✓ Prepared training data in: {training_audio_dir}")
        print(f"\n📖 Next steps:")
        print(f"   1. Start GPT-SoVITS WebUI: python webui.py")
        print(f"   2. Load raw audio from: {training_audio_dir}")
        print(f"   3. Follow training pipeline: Slice -> Denoise -> ASR -> Train")
        print(f"   4. Export model and update reference audio/text")
        
        return str(output_dir)
    
    def set_reference(self, audio_path: str, text: str):
        """Set reference audio and text for voice cloning."""
        self.reference_audio = audio_path
        self.reference_text = text
        print(f"✓ Reference set: {audio_path}")
    
    def synthesize(
        self,
        text: str,
        output_path: str,
        target_duration: Optional[float] = None,
        language: str = "zh",
        top_k: int = 20,
        top_p: float = 0.6,
        temperature: float = 0.6
    ) -> str:
        """
        Synthesize speech using GPT-SoVITS API.
        
        Note: Requires GPT-SoVITS API server running.
        Start with: python api.py -s <sovits_model> -g <gpt_model>
        """
        if not self.reference_audio:
            raise ValueError("Reference audio not set. Call set_reference() first.")
        
        import requests
        
        # GPT-SoVITS API endpoint (default: http://127.0.0.1:9880)
        api_url = "http://127.0.0.1:9880"
        
        try:
            response = requests.post(
                f"{api_url}/",
                json={
                    "text": text,
                    "text_language": language,
                    "ref_audio_path": self.reference_audio,
                    "prompt_text": self.reference_text,
                    "prompt_language": language,
                    "top_k": top_k,
                    "top_p": top_p,
                    "temperature": temperature,
                }
            )
            
            if response.status_code == 200:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                
                # Apply duration constraint if needed
                if target_duration:
                    output_path = self._adjust_duration(output_path, target_duration)
                
                return output_path
            else:
                raise RuntimeError(f"API error: {response.status_code} - {response.text}")
                
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to GPT-SoVITS API at {api_url}. "
                f"Start server with: python api.py -s <sovits_model> -g <gpt_model>"
            )
    
    def _adjust_duration(self, audio_path: str, target_duration: float) -> str:
        """Adjust audio duration using ffmpeg atempo filter."""
        # Get current duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        current_duration = float(result.stdout.strip())
        
        # Calculate speed factor (atempo range: 0.5 - 2.0)
        speed_factor = current_duration / target_duration
        
        if 0.5 <= speed_factor <= 2.0:
            adjusted_path = audio_path.replace(".wav", "_adjusted.wav")
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", audio_path,
                "-af", f"atempo={speed_factor}",
                adjusted_path, "-y"
            ]
            subprocess.run(cmd, check=True)
            return adjusted_path
        else:
            print(f"⚠️  Duration mismatch too large ({speed_factor:.2f}x). Keeping original.")
            return audio_path


class CoquiTTSCloner(VoiceCloner):
    """Coqui TTS XTTS-v2 voice cloning."""
    
    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        try:
            from TTS.api import TTS
            self.tts = TTS(model_name)
            self.speaker_wav = None
        except ImportError:
            raise ImportError("Install Coqui TTS: pip install TTS")
    
    def train(self, audio_files: List[str], output_model_dir: str) -> str:
        """XTTS-v2 uses few-shot learning, no training needed. Just set speaker_wav."""
        print("ℹ️  XTTS-v2 uses zero-shot cloning, no training needed.")
        print(f"   Use the first audio file as reference: {audio_files[0]}")
        self.speaker_wav = audio_files
        return output_model_dir
    
    def synthesize(self, text: str, output_path: str, target_duration: Optional[float] = None, language: str = "zh-cn") -> str:
        if not self.speaker_wav:
            raise ValueError("Speaker reference not set.")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.tts.tts_to_file(
            text=text,
            speaker_wav=self.speaker_wav,
            language=language,
            file_path=output_path
        )
        return output_path


def translate_with_timing(
    segments: List[Dict],
    src_lang: str = "zh",
    tgt_lang: str = "en",
    llm_provider: str = "openai",
    model: str = "gpt-4o",
    api_key: Optional[str] = None
) -> List[Dict]:
    """
    Translate segments with duration constraints.
    
    Args:
        segments: Segments with 'text', 'start', 'end'
        src_lang: Source language code
        tgt_lang: Target language code
        llm_provider: 'openai' or 'anthropic'
        model: Model name
        api_key: API key
    
    Returns:
        Segments with added 'translated_text' field
    """
    if not api_key:
        print("⚠️  No API key, using placeholder translations")
        for seg in segments:
            seg["translated_text"] = seg["text"]
        return segments
    
    # Build prompt with duration constraints
    prompt = f"""请将以下中文文本翻译成{tgt_lang}，并注意：
1. 保持原意准确
2. 译文应该能在相似时长内说完（原文时长已标注）
3. 如果直译会超时，请适当压缩表达

格式：JSON数组，每个对象包含 segment_id 和 translated_text

原文片段：
"""
    
    for idx, seg in enumerate(segments, 1):
        duration = seg["end"] - seg["start"]
        prompt += f"\n{idx}. [{duration:.1f}秒] {seg['text'][:200]}"
    
    try:
        if llm_provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是专业翻译，擅长控制译文长度以匹配视频时长。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            content = response.choices[0].message.content
            
            # Extract JSON
            import re
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            translations = json.loads(content)
            
            for item in translations:
                seg_idx = item["segment_id"] - 1
                if 0 <= seg_idx < len(segments):
                    segments[seg_idx]["translated_text"] = item["translated_text"]
            
            print(f"✓ Translated {len(translations)} segments")
        
    except Exception as e:
        print(f"⚠️  Translation failed: {e}")
        for seg in segments:
            seg["translated_text"] = seg["text"]
    
    return segments


def generate_dubbed_audio(
    segments: List[Dict],
    voice_cloner: VoiceCloner,
    output_dir: str = "output/dubbed_audio"
) -> List[Dict]:
    """
    Generate TTS audio for each translated segment.
    
    Args:
        segments: Segments with 'translated_text', 'start', 'end'
        voice_cloner: VoiceCloner instance
        output_dir: Output directory for audio files
    
    Returns:
        Segments with added 'dubbed_audio_path' field
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for idx, seg in enumerate(segments):
        audio_file = output_path / f"segment_{idx:04d}.wav"
        target_duration = seg["end"] - seg["start"]
        
        try:
            seg["dubbed_audio_path"] = voice_cloner.synthesize(
                text=seg.get("translated_text", seg["text"]),
                output_path=str(audio_file),
                target_duration=target_duration
            )
            print(f"  [{idx+1}/{len(segments)}] Generated: {audio_file.name}")
        except Exception as e:
            print(f"  ⚠️  Failed segment {idx}: {e}")
            seg["dubbed_audio_path"] = None
    
    return segments
