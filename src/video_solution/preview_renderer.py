"""Provider-based rendering for visibly watermarked internal previews."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .content_package import (
    content_package_digest,
    load_content_package,
    validate_content_package,
)


PREVIEW_WIDTH = 1080
PREVIEW_HEIGHT = 1920
PREVIEW_FPS = 25
DEFAULT_VOICE = "zh-CN-YunyangNeural"


class PreviewRenderError(RuntimeError):
    """Raised when an internal preview cannot be rendered."""


@dataclass(frozen=True)
class SpeechArtifact:
    audio_path: Path
    subtitle_path: Path
    duration_seconds: float
    provider: str
    voice: str


@dataclass(frozen=True)
class VideoArtifact:
    video_path: Path
    duration_seconds: float
    provider: str


class SpeechProvider(Protocol):
    def synthesize(self, text: str, output_dir: Path) -> SpeechArtifact:
        """Create narration and timed subtitles for the supplied text."""


class VideoProvider(Protocol):
    def render(
        self,
        *,
        package: dict[str, Any],
        avatar_path: Path,
        speech: SpeechArtifact,
        output_dir: Path,
    ) -> VideoArtifact:
        """Compose a portrait video from the approved inputs."""


class EdgeTTSSpeechProvider:
    """Generic synthetic speech for internal previews; no voice cloning."""

    name = "edge-tts"

    def __init__(self, voice: str = DEFAULT_VOICE) -> None:
        self.voice = voice

    def synthesize(self, text: str, output_dir: Path) -> SpeechArtifact:
        try:
            import edge_tts
        except ImportError as exc:
            raise PreviewRenderError(
                "edge-tts is required; install requirements-preview.txt"
            ) from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / "narration.mp3"
        subtitle_path = output_dir / "subtitles.srt"

        async def generate() -> float:
            communicator = edge_tts.Communicate(text=text, voice=self.voice)
            subtitles = edge_tts.SubMaker()
            duration_ticks = 0
            with audio_path.open("wb") as audio_file:
                async for chunk in communicator.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        subtitles.feed(chunk)
                        duration_ticks = max(
                            duration_ticks,
                            int(chunk["offset"]) + int(chunk["duration"]),
                        )
            if duration_ticks:
                subtitle_path.write_text(subtitles.get_srt(), encoding="utf-8")
                return duration_ticks / 10_000_000
            return 0.0

        try:
            duration_seconds = asyncio.run(generate())
        except Exception as exc:
            raise PreviewRenderError(f"Synthetic speech failed: {exc}") from exc

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise PreviewRenderError("Synthetic speech returned an empty audio file")
        if duration_seconds <= 0:
            duration_seconds = _media_duration(audio_path)
            subtitle_path.write_text(
                _build_sentence_srt(text, duration_seconds), encoding="utf-8"
            )

        return SpeechArtifact(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration_seconds=duration_seconds,
            provider=self.name,
            voice=self.voice,
        )


class FFmpegStaticAvatarProvider:
    """Internal preview provider using a still avatar behind a replaceable interface."""

    name = "ffmpeg-static-avatar-preview"

    def __init__(self, ffmpeg_path: str | Path | None = None) -> None:
        self.ffmpeg_path = Path(ffmpeg_path) if ffmpeg_path else _find_ffmpeg()

    def render(
        self,
        *,
        package: dict[str, Any],
        avatar_path: Path,
        speech: SpeechArtifact,
        output_dir: Path,
    ) -> VideoArtifact:
        if not avatar_path.is_file():
            raise PreviewRenderError(f"Avatar image does not exist: {avatar_path}")

        overlay_path = output_dir / "preview-overlay.png"
        video_path = output_dir / "preview.mp4"
        _create_overlay(package, overlay_path)

        subtitle_filter = _subtitle_filter(speech.subtitle_path)
        filter_graph = (
            f"[0:v]scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:"
            "force_original_aspect_ratio=increase,"
            f"crop={PREVIEW_WIDTH}:{PREVIEW_HEIGHT},setsar=1[avatar];"
            "[avatar][2:v]overlay=0:0:format=auto[framed];"
            f"[framed]{subtitle_filter}[video]"
        )
        command = [
            str(self.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(PREVIEW_FPS),
            "-i",
            str(avatar_path),
            "-i",
            str(speech.audio_path),
            "-loop",
            "1",
            "-framerate",
            str(PREVIEW_FPS),
            "-i",
            str(overlay_path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[video]",
            "-map",
            "1:a:0",
            "-t",
            f"{speech.duration_seconds + 0.25:.3f}",
            "-r",
            str(PREVIEW_FPS),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = result.stderr.strip() or "unknown ffmpeg error"
            raise PreviewRenderError(f"Video composition failed: {message}")
        if not video_path.exists() or video_path.stat().st_size == 0:
            raise PreviewRenderError("Video composition returned an empty file")

        return VideoArtifact(
            video_path=video_path,
            duration_seconds=speech.duration_seconds + 0.25,
            provider=self.name,
        )


class PreviewRenderService:
    """Validate, render, and record one immutable internal-preview attempt."""

    def __init__(self, speech_provider: SpeechProvider, video_provider: VideoProvider) -> None:
        self.speech_provider = speech_provider
        self.video_provider = video_provider

    def render(
        self,
        *,
        package_path: str | Path,
        avatar_path: str | Path,
        output_root: str | Path,
    ) -> Path:
        package_path = Path(package_path).resolve()
        avatar_path = Path(avatar_path).resolve()
        package = load_content_package(package_path)
        digest = content_package_digest(package)
        render_id = _render_id()
        output_dir = (
            Path(output_root).resolve()
            / str(package.get("content_id", "unknown-content"))
            / f"r{package.get('revision', 'unknown')}-{digest[:12]}"
            / render_id
        )
        output_dir.mkdir(parents=True, exist_ok=False)
        manifest_path = output_dir / "render-manifest.json"
        started_at = _now()

        manifest: dict[str, Any] = {
            "schema_version": 1,
            "render_id": render_id,
            "mode": "preview",
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "failure_reason": None,
            "input": {
                "package_path": str(package_path),
                "package_sha256": digest,
                "campaign_id": package.get("campaign_id"),
                "content_id": package.get("content_id"),
                "revision": package.get("revision"),
                "presenter": package.get("presenter"),
                "avatar_path": str(avatar_path),
                "avatar_sha256": _file_sha256(avatar_path) if avatar_path.is_file() else None,
            },
            "configuration": {
                "width": PREVIEW_WIDTH,
                "height": PREVIEW_HEIGHT,
                "fps": PREVIEW_FPS,
                "watermark": "PREVIEW / 仅供内部审核",
                "target_channels": package.get("target_channels"),
            },
            "providers": {},
            "outputs": {},
        }
        _write_manifest(manifest_path, manifest)

        try:
            issues = validate_content_package(package, mode="preview")
            errors = [issue for issue in issues if issue.severity == "error"]
            if errors:
                detail = "; ".join(f"{issue.path}: {issue.message}" for issue in errors)
                raise PreviewRenderError(f"Content package failed preview validation: {detail}")
            if "internal_preview" not in package.get("target_channels", []):
                raise PreviewRenderError(
                    "Internal preview rendering requires target_channels to include internal_preview"
                )
            if not avatar_path.is_file():
                raise PreviewRenderError(f"Avatar image does not exist: {avatar_path}")

            shutil.copy2(package_path, output_dir / "input-package.json")
            speech = self.speech_provider.synthesize(package["script"], output_dir)
            video = self.video_provider.render(
                package=package,
                avatar_path=avatar_path,
                speech=speech,
                output_dir=output_dir,
            )

            manifest["status"] = "completed"
            manifest["completed_at"] = _now()
            manifest["duration_seconds"] = round(video.duration_seconds, 3)
            manifest["providers"] = {
                "speech": {"name": speech.provider, "voice": speech.voice},
                "video": {"name": video.provider},
            }
            manifest["outputs"] = {
                "video": _output_record(video.video_path),
                "audio": _output_record(speech.audio_path),
                "subtitles": _output_record(speech.subtitle_path),
            }
            _write_manifest(manifest_path, manifest)
            return manifest_path
        except Exception as exc:
            manifest["status"] = "failed"
            manifest["completed_at"] = _now()
            manifest["failure_reason"] = str(exc)
            _write_manifest(manifest_path, manifest)
            if isinstance(exc, PreviewRenderError):
                raise
            raise PreviewRenderError(str(exc)) from exc


def _find_ffmpeg() -> Path:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return Path(system_ffmpeg)
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise PreviewRenderError(
            "ffmpeg was not found; install requirements-preview.txt"
        ) from exc
    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def _media_duration(path: Path) -> float:
    command = [
        str(_find_ffmpeg()),
        "-hide_banner",
        "-i",
        str(path),
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise PreviewRenderError("Could not determine synthetic speech duration")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise PreviewRenderError("Synthetic speech returned invalid duration")
    return duration


def _build_sentence_srt(text: str, duration_seconds: float) -> str:
    raw_clauses = [
        clause.strip()
        for clause in re.findall(r"[^。！？；，,.!?;]+[。！？；，,.!?;]?", text)
        if clause.strip()
    ]
    clauses = [
        chunk
        for clause in raw_clauses
        for chunk in _split_long_clause(clause, max_characters=14)
    ]
    if not clauses:
        clauses = [text.strip()]
    total_characters = sum(max(len(clause), 1) for clause in clauses)
    cursor = 0.0
    entries: list[str] = []
    for index, clause in enumerate(clauses, start=1):
        share = duration_seconds * max(len(clause), 1) / total_characters
        end = duration_seconds if index == len(clauses) else cursor + share
        entries.append(
            f"{index}\n{_srt_time(cursor)} --> {_srt_time(end)}\n{clause}\n"
        )
        cursor = end
    return "\n".join(entries)


def _split_long_clause(clause: str, max_characters: int) -> list[str]:
    if len(clause) <= max_characters:
        return [clause]
    return [
        clause[index : index + max_characters]
        for index in range(0, len(clause), max_characters)
    ]


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _create_overlay(package: dict[str, Any], output_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise PreviewRenderError(
            "Pillow is required; install requirements-preview.txt"
        ) from exc

    image = Image.new("RGBA", (PREVIEW_WIDTH, PREVIEW_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    regular_font = _font(ImageFont, 34)
    title_font = _font(ImageFont, 54, bold=True)
    watermark_font = _font(ImageFont, 112, bold=True)

    draw.rounded_rectangle((48, 44, 486, 102), radius=12, fill=(12, 20, 28, 218))
    draw.text((72, 57), "高考内容 · 内部预览", font=regular_font, fill=(255, 255, 255, 255))

    title_lines = _wrap_text(draw, str(package.get("title", "")), title_font, 920)
    title_height = len(title_lines) * 72 + 44
    draw.rounded_rectangle(
        (48, 126, 1032, 126 + title_height),
        radius=16,
        fill=(12, 20, 28, 200),
    )
    for index, line in enumerate(title_lines):
        draw.text(
            (78, 148 + index * 72),
            line,
            font=title_font,
            fill=(255, 255, 255, 255),
        )

    watermark = Image.new("RGBA", (900, 260), (0, 0, 0, 0))
    watermark_draw = ImageDraw.Draw(watermark, "RGBA")
    watermark_draw.text(
        (70, 50),
        "PREVIEW",
        font=watermark_font,
        fill=(255, 255, 255, 70),
        stroke_width=3,
        stroke_fill=(0, 0, 0, 45),
    )
    watermark = watermark.rotate(20, expand=True)
    image.alpha_composite(watermark, (70, 670))

    draw.rounded_rectangle((48, 1760, 1032, 1878), radius=16, fill=(12, 20, 28, 218))
    draw.text(
        (74, 1780),
        "AI 合成人物与声音 · 仅供内部审核 · 禁止发布",
        font=regular_font,
        fill=(255, 255, 255, 255),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _font(image_font: Any, size: int, bold: bool = False) -> Any:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return image_font.truetype(str(candidate), size=size)
    return image_font.load_default(size=size)


def _wrap_text(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3] or [""]


def _subtitle_filter(subtitle_path: Path) -> str:
    path = _ffmpeg_filter_path(subtitle_path)
    style = (
        "FontName=Microsoft YaHei,FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00202020,BackColour=&H90000000,BorderStyle=3,"
        "Outline=1,Shadow=0,Alignment=2,MarginL=24,MarginR=24,MarginV=48"
    )
    return f"subtitles=filename='{path}':force_style='{style}'"


def _ffmpeg_filter_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace(":", r"\:").replace("'", r"\'")


def _render_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _output_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": _file_sha256(path),
        "bytes": path.stat().st_size,
    }


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
