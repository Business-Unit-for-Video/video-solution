"""Validation for business-owned video and live-stream content packages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse


CONTENT_TYPES = {"short_video", "live_segment"}
MODES = {"validate", "preview", "production", "live-package"}
RISK_LEVELS = {"low", "medium", "high"}
STATUSES = {"draft", "reviewed", "approved", "rejected", "published"}
SOURCE_REVIEW_STATUSES = {"pending", "approved", "rejected"}
RIGHTS_STATUSES = {"pending", "active", "expired", "revoked"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FORBIDDEN_PERSONAL_FIELDS = {
    "contact",
    "email",
    "exam_number",
    "id_card",
    "mobile",
    "personal_grade",
    "personal_rank",
    "phone",
    "student_id",
    "student_name",
    "wechat",
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


def load_content_package(path: str | Path) -> dict[str, Any]:
    """Load a JSON content package from disk."""
    package_path = Path(path)
    try:
        data = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {package_path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(f"Content package must be a JSON object: {package_path}")
    return data


def content_package_digest(package: dict[str, Any]) -> str:
    """Return a stable SHA-256 digest for an exact package revision."""
    canonical = json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_content_package(
    package: dict[str, Any], mode: str = "validate"
) -> list[ValidationIssue]:
    """Validate a package for intake, preview, production, or live packaging."""
    issues: list[ValidationIssue] = []
    if mode not in MODES:
        return [
            ValidationIssue(
                "invalid_mode", "mode", f"Mode must be one of: {', '.join(sorted(MODES))}"
            )
        ]

    _require_value(package, "schema_version", issues)
    _require_text(package, "campaign_id", issues)
    _require_text(package, "content_id", issues)
    _require_value(package, "revision", issues)
    for field in ("audience", "title", "hook", "script", "risk_disclosure"):
        _require_text(package, field, issues)

    if package.get("schema_version") != 1:
        issues.append(
            ValidationIssue(
                "unsupported_schema", "schema_version", "Only schema_version 1 is supported"
            )
        )

    for field in ("campaign_id", "content_id"):
        value = package.get(field)
        if isinstance(value, str) and value and not SLUG_PATTERN.fullmatch(value):
            issues.append(
                ValidationIssue(
                    "invalid_slug",
                    field,
                    "Use lowercase letters, digits, and single hyphens",
                )
            )

    revision = package.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        issues.append(
            ValidationIssue(
                "invalid_revision", "revision", "Revision must be a positive integer"
            )
        )

    _check_enum(package, "content_type", CONTENT_TYPES, issues)
    _check_enum(package, "risk_level", RISK_LEVELS, issues)
    _check_enum(package, "status", STATUSES, issues)
    _validate_text_list(package.get("target_channels"), "target_channels", issues)

    _validate_cta(package.get("cta"), package, issues)
    _validate_sources(package.get("sources"), issues)
    _validate_handoffs(package, issues)
    _validate_rights(package.get("rights"), issues)
    _validate_review(package, issues)
    _find_personal_fields(package, "$", issues)

    status = package.get("status")
    if status == "rejected" and mode != "validate":
        issues.append(
            ValidationIssue(
                "rejected_package", "status", "Rejected content cannot be previewed or rendered"
            )
        )

    if mode == "preview" and status not in {"draft", "reviewed", "approved", "published"}:
        issues.append(
            ValidationIssue(
                "preview_blocked", "status", "Preview requires draft, reviewed, or approved content"
            )
        )

    if mode in {"production", "live-package"}:
        _validate_production_readiness(package, issues)

    if mode == "live-package" and package.get("content_type") != "live_segment":
        issues.append(
            ValidationIssue(
                "not_live_segment",
                "content_type",
                "live-package mode accepts only live_segment content",
            )
        )

    return _deduplicate(issues)


def build_validation_report(
    package: dict[str, Any], mode: str, issues: Iterable[ValidationIssue]
) -> dict[str, Any]:
    issue_list = list(issues)
    return {
        "valid": not any(issue.severity == "error" for issue in issue_list),
        "mode": mode,
        "campaign_id": package.get("campaign_id"),
        "content_id": package.get("content_id"),
        "revision": package.get("revision"),
        "package_sha256": content_package_digest(package),
        "issues": [asdict(issue) for issue in issue_list],
    }


def _require_value(
    data: dict[str, Any], field: str, issues: list[ValidationIssue]
) -> None:
    if field not in data or data[field] is None:
        issues.append(ValidationIssue("required", field, "Field is required"))


def _require_text(
    data: dict[str, Any], field: str, issues: list[ValidationIssue]
) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue("required_text", field, "Non-empty text is required"))


def _check_enum(
    data: dict[str, Any],
    field: str,
    allowed: set[str],
    issues: list[ValidationIssue],
) -> None:
    if data.get(field) not in allowed:
        issues.append(
            ValidationIssue(
                "invalid_value", field, f"Value must be one of: {', '.join(sorted(allowed))}"
            )
        )


def _validate_cta(
    cta: Any, package: dict[str, Any], issues: list[ValidationIssue]
) -> None:
    if not isinstance(cta, dict):
        issues.append(ValidationIssue("invalid_cta", "cta", "CTA must be an object"))
        return

    for field in ("label", "url"):
        value = cta.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(
                ValidationIssue(
                    "required_text", f"cta.{field}", "Non-empty text is required"
                )
            )

    url = cta.get("url")
    if not isinstance(url, str) or not url.strip():
        return
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        issues.append(
            ValidationIssue("invalid_url", "cta.url", "CTA URL must be an absolute HTTP(S) URL")
        )
        return

    query = parse_qs(parsed.query)
    for field in ("campaign_id", "content_id"):
        expected = package.get(field)
        if expected and query.get(field) != [expected]:
            issues.append(
                ValidationIssue(
                    "missing_attribution",
                    f"cta.url.{field}",
                    f"CTA URL must include {field}={expected}",
                )
            )


def _validate_sources(sources: Any, issues: list[ValidationIssue]) -> None:
    if not isinstance(sources, list) or not sources:
        issues.append(
            ValidationIssue("missing_sources", "sources", "At least one source is required")
        )
        return

    required = (
        "source_id",
        "publisher",
        "title",
        "location",
        "version",
        "retrieved_at",
        "applicability",
        "review_status",
    )
    for index, source in enumerate(sources):
        path = f"sources[{index}]"
        if not isinstance(source, dict):
            issues.append(ValidationIssue("invalid_source", path, "Source must be an object"))
            continue
        for field in required:
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(
                    ValidationIssue("required_text", f"{path}.{field}", "Non-empty text is required")
                )
        status = source.get("review_status")
        if status not in SOURCE_REVIEW_STATUSES:
            issues.append(
                ValidationIssue(
                    "invalid_source_status",
                    f"{path}.review_status",
                    f"Value must be one of: {', '.join(sorted(SOURCE_REVIEW_STATUSES))}",
                )
            )
        retrieved_at = source.get("retrieved_at")
        if isinstance(retrieved_at, str) and retrieved_at:
            _validate_datetime(retrieved_at, f"{path}.retrieved_at", issues)


def _validate_handoffs(
    package: dict[str, Any], issues: list[ValidationIssue]
) -> None:
    handoffs = package.get("handoff_topics")
    if not isinstance(handoffs, list):
        issues.append(
            ValidationIssue(
                "invalid_handoffs", "handoff_topics", "handoff_topics must be an array"
            )
        )
        return
    if any(not isinstance(item, str) or not item.strip() for item in handoffs):
        issues.append(
            ValidationIssue(
                "invalid_handoff_topic",
                "handoff_topics",
                "Every handoff topic must be non-empty text",
            )
        )
    if package.get("risk_level") == "high" and not handoffs:
        issues.append(
            ValidationIssue(
                "missing_high_risk_handoff",
                "handoff_topics",
                "High-risk content requires at least one human handoff topic",
            )
        )


def _validate_text_list(
    value: Any, path: str, issues: list[ValidationIssue]
) -> None:
    if not isinstance(value, list) or not value:
        issues.append(
            ValidationIssue(
                "invalid_text_list", path, "At least one non-empty text value is required"
            )
        )
        return
    if any(not isinstance(item, str) or not item.strip() for item in value):
        issues.append(
            ValidationIssue(
                "invalid_text_list", path, "Every list item must be non-empty text"
            )
        )


def _validate_rights(rights: Any, issues: list[ValidationIssue]) -> None:
    if rights is None:
        return
    if not isinstance(rights, list):
        issues.append(ValidationIssue("invalid_rights", "rights", "rights must be an array"))
        return

    required = (
        "asset_type",
        "asset_id",
        "rights_basis",
        "evidence_ref",
        "allowed_uses",
        "owner",
        "status",
    )
    for index, right in enumerate(rights):
        path = f"rights[{index}]"
        if not isinstance(right, dict):
            issues.append(ValidationIssue("invalid_right", path, "Rights record must be an object"))
            continue
        for field in required:
            value = right.get(field)
            if field == "allowed_uses":
                if not isinstance(value, list) or not value or any(
                    not isinstance(item, str) or not item.strip() for item in value
                ):
                    issues.append(
                        ValidationIssue(
                            "invalid_allowed_uses",
                            f"{path}.{field}",
                            "allowed_uses must contain at least one non-empty value",
                        )
                    )
            elif not isinstance(value, str) or not value.strip():
                issues.append(
                    ValidationIssue("required_text", f"{path}.{field}", "Non-empty text is required")
                )
        if right.get("status") not in RIGHTS_STATUSES:
            issues.append(
                ValidationIssue(
                    "invalid_rights_status",
                    f"{path}.status",
                    f"Value must be one of: {', '.join(sorted(RIGHTS_STATUSES))}",
                )
            )


def _validate_review(
    package: dict[str, Any], issues: list[ValidationIssue]
) -> None:
    review = package.get("review")
    if not isinstance(review, dict):
        issues.append(ValidationIssue("invalid_review", "review", "review must be an object"))
        return

    status = package.get("status")
    required_fields: tuple[str, ...] = ()
    if status == "reviewed":
        required_fields = ("reviewed_by", "reviewed_at")
    elif status in {"approved", "published"}:
        required_fields = ("reviewed_by", "reviewed_at", "approved_by", "approved_at")

    for field in required_fields:
        value = review.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(
                ValidationIssue("missing_approval", f"review.{field}", "Review metadata is required")
            )

    if status in {"reviewed", "approved", "published"}:
        timestamp_fields = ("reviewed_at",)
        if status in {"approved", "published"}:
            timestamp_fields += ("approved_at",)
        for field in timestamp_fields:
            value = review.get(field)
            if isinstance(value, str) and value:
                _validate_datetime(value, f"review.{field}", issues)


def _validate_production_readiness(
    package: dict[str, Any], issues: list[ValidationIssue]
) -> None:
    if package.get("status") not in {"approved", "published"}:
        issues.append(
            ValidationIssue(
                "production_not_approved",
                "status",
                "Production requires approved or published content",
            )
        )

    sources = package.get("sources")
    if isinstance(sources, list):
        for index, source in enumerate(sources):
            if isinstance(source, dict) and source.get("review_status") != "approved":
                issues.append(
                    ValidationIssue(
                        "source_not_approved",
                        f"sources[{index}].review_status",
                        "Production requires every source to be approved",
                    )
                )

    cta = package.get("cta")
    if isinstance(cta, dict) and isinstance(cta.get("url"), str):
        hostname = urlparse(cta["url"]).hostname or ""
        if hostname.endswith(".invalid"):
            issues.append(
                ValidationIssue(
                    "placeholder_cta",
                    "cta.url",
                    "Production requires a real lead-capture URL",
                )
            )


def _validate_datetime(
    value: str, path: str, issues: list[ValidationIssue]
) -> None:
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        issues.append(
            ValidationIssue(
                "invalid_datetime", path, "Use an ISO 8601 date or timestamp"
            )
        )


def _find_personal_fields(
    value: Any, path: str, issues: list[ValidationIssue]
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_PERSONAL_FIELDS:
                issues.append(
                    ValidationIssue(
                        "personal_data_forbidden",
                        child_path,
                        "Student/contact personal data must not be stored in a Video content package",
                    )
                )
            _find_personal_fields(child, child_path, issues)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _find_personal_fields(child, f"{path}[{index}]", issues)


def _deduplicate(issues: Iterable[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[ValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.path, issue.message, issue.severity)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
