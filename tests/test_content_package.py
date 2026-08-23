import copy
import unittest

from src.video_solution.content_package import (
    build_validation_report,
    content_package_digest,
    validate_content_package,
)


def approved_package():
    return {
        "schema_version": 1,
        "campaign_id": "gaokao-2027-shaanxi-pilot",
        "content_id": "rank-vs-score-001",
        "content_type": "short_video",
        "revision": 1,
        "target_channels": ["internal_preview"],
        "audience": "陕西 2027 届高三学生家长",
        "title": "模考分数为什么不能直接等于高考位次",
        "hook": "同样的分数，在不同考试里可能代表不同的位置。",
        "script": "正式脚本由已审核资料生成，并由高考咨询师复核。",
        "risk_disclosure": "阶段性判断仅供准备参考，正式方案需要人工复核。",
        "cta": {
            "label": "领取准备清单",
            "url": "https://example.com/gaokao?campaign_id=gaokao-2027-shaanxi-pilot&content_id=rank-vs-score-001",
        },
        "sources": [
            {
                "source_id": "gaokao-kb-001",
                "publisher": "Gaokao knowledge base",
                "title": "位次与分数使用说明",
                "location": "repo://Business-Unit-for-Gaokao/gaokao-knowledge-base/rank.md",
                "version": "2026-08-04",
                "retrieved_at": "2026-08-04",
                "applicability": "陕西/2027 届",
                "review_status": "approved",
            }
        ],
        "risk_level": "high",
        "handoff_topics": ["具体省位次预测", "录取概率", "最终志愿方案"],
        "rights": [
            {
                "asset_type": "avatar_and_voice",
                "asset_id": "gaokao-host-01",
                "rights_basis": "written_consent",
                "evidence_ref": "manual-review://gaokao-host-01",
                "allowed_uses": ["recorded_video", "supervised_live"],
                "owner": "Gaokao business unit",
                "status": "active",
            }
        ],
        "status": "approved",
        "review": {
            "reviewed_by": "gaokao-consultant",
            "reviewed_at": "2026-08-04T10:00:00+08:00",
            "approved_by": "gaokao-owner",
            "approved_at": "2026-08-04T11:00:00+08:00",
        },
    }


class ContentPackageValidationTests(unittest.TestCase):
    def test_approved_package_is_production_ready(self):
        issues = validate_content_package(approved_package(), mode="production")
        self.assertEqual([], issues)

    def test_draft_is_blocked_from_production(self):
        package = approved_package()
        package["status"] = "draft"
        package["review"] = {}
        package["sources"][0]["review_status"] = "pending"
        package["rights"] = []

        issues = validate_content_package(package, mode="production")
        codes = {issue.code for issue in issues}
        self.assertIn("production_not_approved", codes)
        self.assertIn("source_not_approved", codes)
        self.assertNotIn("missing_production_rights", codes)

    def test_high_risk_content_requires_handoff_topics(self):
        package = approved_package()
        package["handoff_topics"] = []

        issues = validate_content_package(package)

        self.assertIn("missing_high_risk_handoff", {issue.code for issue in issues})

    def test_cta_must_include_campaign_and_content_ids(self):
        package = approved_package()
        package["cta"]["url"] = "https://example.com/gaokao"

        issues = validate_content_package(package)

        attribution_paths = {
            issue.path for issue in issues if issue.code == "missing_attribution"
        }
        self.assertEqual(
            {"cta.url.campaign_id", "cta.url.content_id"}, attribution_paths
        )

    def test_personal_data_field_is_rejected(self):
        package = approved_package()
        package["student_name"] = "Example Student"

        issues = validate_content_package(package)

        self.assertIn("personal_data_forbidden", {issue.code for issue in issues})

    def test_live_mode_requires_live_segment(self):
        issues = validate_content_package(approved_package(), mode="live-package")
        self.assertIn("not_live_segment", {issue.code for issue in issues})

    def test_production_does_not_require_automated_rights_gate(self):
        package = approved_package()
        package["rights"] = []

        issues = validate_content_package(package, mode="production")
        self.assertEqual([], issues)

    def test_production_rejects_placeholder_cta(self):
        package = approved_package()
        package["cta"]["url"] = (
            "https://example.invalid/gaokao"
            "?campaign_id=gaokao-2027-shaanxi-pilot"
            "&content_id=rank-vs-score-001"
        )

        issues = validate_content_package(package, mode="production")
        self.assertIn("placeholder_cta", {issue.code for issue in issues})

    def test_digest_is_stable_across_key_order(self):
        package = approved_package()
        reordered = dict(reversed(list(copy.deepcopy(package).items())))
        self.assertEqual(
            content_package_digest(package), content_package_digest(reordered)
        )

    def test_report_marks_errors_invalid(self):
        package = approved_package()
        package["revision"] = 0
        issues = validate_content_package(package)
        report = build_validation_report(package, "validate", issues)

        self.assertFalse(report["valid"])
        self.assertEqual(64, len(report["package_sha256"]))


if __name__ == "__main__":
    unittest.main()
