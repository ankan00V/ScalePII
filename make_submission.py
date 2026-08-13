#!/usr/bin/env python3
"""Build the minimal, reviewer-ready assignment archive.

The archive contains only the requested deliverables, the implementation,
self-contained tests and current evidence. It intentionally excludes the raw
prospectus, annotation source data, working notes, caches and legacy reports.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "PII_Redaction_Submission.zip"
PREFIX = "PII_Redaction_Submission"

FILES = (
    "README.md",
    "EVALUATION.md",
    "SUBMISSION.md",
    "REVIEWER_GUIDE.md",
    "requirements.txt",
    "redact.py",
    "evaluate.py",
    "verify_delivery.py",
    "make_submission.py",
    "piiredact",
    "assets",
    "tests",
    "output/Red Herring Prospectus - REDACTED.docx",
    "output/mapping.csv",
    "output/detections.jsonl",
    "output/field_code_redactions.json",
    "output/media_redactions.json",
    "reports/README.md",
    "reports/run_summary.json",
    "reports/evaluation.json",
    "reports/evaluation_heldout.json",
    "reports/evaluation_coverage.json",
)


def _files_to_archive() -> list[Path]:
    files: list[Path] = []
    for relative in FILES:
        path = ROOT / relative
        if not path.exists():
            raise FileNotFoundError(f"submission input is missing: {path}")
        if path.is_file():
            files.append(path)
        else:
            files.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file()
                and "__pycache__" not in candidate.parts
                and candidate.suffix != ".pyc"
                and candidate.name != ".DS_Store"
            )
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def _manifest_entry(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> None:
    files = _files_to_archive()
    manifest = {
        "archive_root": PREFIX,
        "files": [_manifest_entry(path) for path in files],
        "excluded": [
            "CONTEXT.md",
            "input.docx and gold/ (raw source PII / annotation data)",
            "__pycache__/ and *.pyc",
            "reports/evaluation_heldout_blind.json",
            "reports/evaluation_coverage_blind.json",
        ],
    }
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for path in files:
            package.write(path, f"{PREFIX}/{path.relative_to(ROOT).as_posix()}")
        package.writestr(
            f"{PREFIX}/MANIFEST.json",
            json.dumps(manifest, indent=2) + "\n",
        )

    print(f"Created {ARCHIVE.name}: {len(files)} files")
    print(f"SHA-256: {hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
