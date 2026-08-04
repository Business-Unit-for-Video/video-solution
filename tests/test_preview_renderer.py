import json
import tempfile
import unittest
from pathlib import Path

from src.video_solution.preview_renderer import (
    PREVIEW_HEIGHT,
    PREVIEW_WIDTH,
    PreviewRenderError,
    PreviewRenderService,
    SpeechArtifact,
    VideoArtifact,
    _build_sentence_srt,
)


def draft_package():
    return {
        "schema_version": 1,
        "campaign_id": "gaokao-2027-shaanxi-pilot",
        "content_id": "rank-vs-score-001",
        "content_type": "short_video",
        "revision": 1,
        "target_channels": ["internal_preview"],
        "audience": "陕西 2027 届高三学生家长",
        "title": "模考分数为什么不能直接等于高考位次",
        "hook": "同样的分数可能代表不同的位置。",
        "script": "这是内部预览脚本。",
        "risk_disclosure": "阶段性判断仅供准备参考。",
        "cta": {
            "label": "领取准备清单",
            "url": (
                "https://example.invalid/gaokao"
                "?campaign_id=gaokao-2027-shaanxi-pilot"
                "&content_id=rank-vs-score-001"
            ),
        },
        "sources": [
            {
                "source_id": "gaokao-kb-001",
                "publisher": "Gaokao knowledge base",
                "title": "位次",
                "location": "repo://gaokao-knowledge-base/rank.md",
                "version": "test",
                "retrieved_at": "2026-08-04",
                "applicability": "陕西/2027 届",
                "review_status": "pending",
            }
        ],
        "risk_level": "high",
        "handoff_topics": ["具体位次预测"],
        "rights": [],
        "status": "draft",
        "review": {},
    }


class FakeSpeechProvider:
    def synthesize(self, text: str, output_dir: Path) -> SpeechArtifact:
        audio_path = output_dir / "narration.mp3"
        subtitle_path = output_dir / "subtitles.srt"
        audio_path.write_bytes(b"fake-audio")
        subtitle_path.write_text(
            "1\n00:00:00,000 --> 00:00:03,000\n" + text + "\n",
            encoding="utf-8",
        )
        return SpeechArtifact(
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            duration_seconds=3.0,
            provider="fake-speech",
            voice="generic-test-voice",
        )


class FakeVideoProvider:
    def render(
        self,
        *,
        package,
        avatar_path: Path,
        speech: SpeechArtifact,
        output_dir: Path,
    ) -> VideoArtifact:
        video_path = output_dir / "preview.mp4"
        video_path.write_bytes(b"fake-video")
        return VideoArtifact(
            video_path=video_path,
            duration_seconds=speech.duration_seconds,
            provider="fake-video",
        )


class FailingVideoProvider:
    def render(self, **kwargs):
        raise PreviewRenderError("test composition failure")


class PreviewRenderServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.package_path = self.root / "package.json"
        self.avatar_path = self.root / "avatar.png"
        self.output_root = self.root / "output"
        self.package_path.write_text(
            json.dumps(draft_package(), ensure_ascii=False), encoding="utf-8"
        )
        self.avatar_path.write_bytes(b"fake-avatar")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_completed_manifest_is_traceable_and_watermarked(self):
        service = PreviewRenderService(FakeSpeechProvider(), FakeVideoProvider())

        manifest_path = service.render(
            package_path=self.package_path,
            avatar_path=self.avatar_path,
            output_root=self.output_root,
        )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("completed", manifest["status"])
        self.assertEqual("preview", manifest["mode"])
        self.assertEqual(PREVIEW_WIDTH, manifest["configuration"]["width"])
        self.assertEqual(PREVIEW_HEIGHT, manifest["configuration"]["height"])
        self.assertIn("PREVIEW", manifest["configuration"]["watermark"])
        self.assertEqual("fake-speech", manifest["providers"]["speech"]["name"])
        self.assertEqual("fake-video", manifest["providers"]["video"]["name"])
        self.assertEqual(64, len(manifest["input"]["package_sha256"]))
        self.assertEqual(64, len(manifest["outputs"]["video"]["sha256"]))
        self.assertTrue((manifest_path.parent / "input-package.json").is_file())

    def test_non_internal_channel_is_blocked(self):
        package = draft_package()
        package["target_channels"] = ["douyin"]
        self.package_path.write_text(
            json.dumps(package, ensure_ascii=False), encoding="utf-8"
        )
        service = PreviewRenderService(FakeSpeechProvider(), FakeVideoProvider())

        with self.assertRaisesRegex(PreviewRenderError, "internal_preview"):
            service.render(
                package_path=self.package_path,
                avatar_path=self.avatar_path,
                output_root=self.output_root,
            )

        manifest_path = next(self.output_root.rglob("render-manifest.json"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["status"])

    def test_provider_failure_is_recorded(self):
        service = PreviewRenderService(FakeSpeechProvider(), FailingVideoProvider())

        with self.assertRaisesRegex(PreviewRenderError, "test composition failure"):
            service.render(
                package_path=self.package_path,
                avatar_path=self.avatar_path,
                output_root=self.output_root,
            )

        manifest_path = next(self.output_root.rglob("render-manifest.json"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["status"])
        self.assertEqual("test composition failure", manifest["failure_reason"])

    def test_missing_avatar_is_recorded(self):
        service = PreviewRenderService(FakeSpeechProvider(), FakeVideoProvider())
        missing = self.root / "missing.png"

        with self.assertRaisesRegex(PreviewRenderError, "does not exist"):
            service.render(
                package_path=self.package_path,
                avatar_path=missing,
                output_root=self.output_root,
            )

        manifest_path = next(self.output_root.rglob("render-manifest.json"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["status"])

    def test_sentence_subtitle_fallback_covers_audio_duration(self):
        subtitle = _build_sentence_srt("第一句。第二句，继续。", 9.5)

        self.assertIn("00:00:00,000", subtitle)
        self.assertIn("00:00:09,500", subtitle)
        self.assertIn("第一句。", subtitle)
        self.assertIn("第二句，", subtitle)

    def test_sentence_subtitle_fallback_splits_long_chinese_clauses(self):
        subtitle = _build_sentence_srt("这是一句超过十四个汉字的内部预览字幕内容。", 6.0)
        caption_lines = [
            line
            for line in subtitle.splitlines()
            if line and "-->" not in line and not line.isdigit()
        ]

        self.assertGreater(len(caption_lines), 1)
        self.assertTrue(all(len(line) <= 14 for line in caption_lines))


if __name__ == "__main__":
    unittest.main()
