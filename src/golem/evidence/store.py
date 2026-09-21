from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from golem.core.models import EvidenceRef
from golem.core.serialization import stable_json

SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"(?i)(authorization|password|passwd|token|api[_-]?key|secret|cookie)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(postgres|mysql|mongodb(?:\+srv)?)://\S+"),
)
FORBIDDEN_FIELDS = {"raw_prompt", "prompt", "prompt_text", "environment", "raw_data", "response_body"}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def validate_safe_payload(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_FIELDS:
                errors.append(f"Forbidden evidence field: {path}.{key}")
            errors.extend(validate_safe_payload(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(validate_safe_payload(item, f"{path}[{index}]"))
    elif isinstance(value, str) and redact(value) != value:
        errors.append(f"Unredacted sensitive value: {path}")
    return errors


@dataclass(frozen=True)
class EvidenceStore:
    root: Path

    def put(self, kind: str, payload: dict[str, Any]) -> EvidenceRef:
        safe_payload = _redacted(payload)
        errors = validate_safe_payload(safe_payload)
        if errors:
            raise ValueError("; ".join(errors))
        envelope = {
            "schema_version": 1,
            "kind": kind,
            "payload": safe_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        digest_input = {key: value for key, value in envelope.items() if key != "created_at"}
        digest = "sha256:" + sha256_text(stable_json(digest_input))
        envelope["evidence_digest"] = digest
        target = self.root / "content-addressed" / f"{digest.split(':', 1)[1]}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(stable_json(envelope) + "\n", encoding="utf-8")
        return EvidenceRef(digest=digest, kind=kind, uri=str(target))

    def verify(self, ref: EvidenceRef) -> list[str]:
        path = Path(ref.uri)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ["Evidence cannot be read as JSON."]
        claimed = envelope.get("evidence_digest")
        digest_input = {key: value for key, value in envelope.items() if key not in {"created_at", "evidence_digest"}}
        actual = "sha256:" + sha256_text(stable_json(digest_input))
        errors = validate_safe_payload(envelope)
        if claimed != actual:
            errors.append("Evidence digest mismatch.")
        if path.stem != actual.split(":", 1)[1]:
            errors.append("Evidence filename does not match digest.")
        if claimed != ref.digest:
            errors.append("Evidence ref digest does not match payload.")
        return errors


def _redacted(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redacted(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value
