#!/usr/bin/env python3
"""CLI entrypoint for the PII redaction tool.

    python redact.py --input input.docx --output output/redacted.docx

Writes the redacted .docx plus privacy-safe audit artefacts next to it:
``mapping.csv`` (a one-way source hash and its fake replacement),
``detections.jsonl`` (detector, hash and location for every text span), and
``field_code_redactions.json`` (redacted hyperlink/mailto instructions) and
``media_redactions.json`` (the embedded image parts that were neutralised).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path


def load_nlp(model: str = "en_core_web_sm"):
    """Load spaCy with only the components NER needs."""
    try:
        import spacy
    except ImportError:
        print("spaCy not installed; running regex-only.", file=sys.stderr)
        return None
    try:
        return spacy.load(model, exclude=["parser", "lemmatizer", "attribute_ruler", "tagger"])
    except OSError:
        print(
            f"spaCy model '{model}' not found. Install it with:\n"
            f"    python -m spacy download {model}\n"
            "Falling back to regex-only detection (person/organisation recall "
            "will drop sharply).",
            file=sys.stderr,
        )
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="input.docx", help="source .docx")
    parser.add_argument(
        "--output", default="output/redacted.docx", help="destination .docx"
    )
    parser.add_argument("--model", default="en_core_web_sm", help="spaCy model")
    parser.add_argument(
        "--seed", type=int, default=20251210, help="seed for reproducible fakes"
    )
    parser.add_argument(
        "--no-ner", action="store_true", help="regex/gazetteer only, skip spaCy"
    )
    parser.add_argument(
        "--keep-images",
        action="store_true",
        help="do not redact embedded images (unsafe for documents that contain image PII)",
    )
    parser.add_argument(
        "--report", default="reports/run_summary.json", help="run summary JSON"
    )
    args = parser.parse_args()

    from piiredact import redact

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)

    nlp = None if args.no_ner else load_nlp(args.model)

    started = time.time()
    result = redact(
        args.input,
        str(output_path),
        nlp=nlp,
        seed=args.seed,
        redact_images=not args.keep_images,
    )
    elapsed = time.time() - started

    mapping = result.pop("mapping")
    detections = result.pop("detections")
    field_code_redactions = result.pop("field_code_redactions")
    media_redactions = result.pop("media_redactions")

    mapping_path = output_path.parent / "mapping.csv"
    with mapping_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["entity_type", "source_sha256", "replacement"],
        )
        writer.writeheader()
        writer.writerows(mapping)

    detections_path = output_path.parent / "detections.jsonl"
    with detections_path.open("w", encoding="utf-8") as handle:
        for row in detections:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    media_path = output_path.parent / "media_redactions.json"
    media_path.write_text(json.dumps(media_redactions, indent=2), encoding="utf-8")

    field_code_path = output_path.parent / "field_code_redactions.json"
    field_code_path.write_text(
        json.dumps(field_code_redactions, indent=2), encoding="utf-8"
    )

    result["elapsed_seconds"] = round(elapsed, 2)
    # A stable mapping may deliberately coalesce presentation variants of the
    # same source value (for example, punctuation variants of an organisation
    # name). Call this what it is rather than falsely claiming a raw-value
    # count.
    result["stable_mappings"] = len(mapping)
    Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Redacted -> {output_path}")
    print(f"  blocks scanned   : {result['blocks_scanned']}")
    print(f"  blocks modified  : {result['blocks_touched']}")
    print(f"  replacements     : {result['replacements']}")
    print(f"  stable mappings  : {result['stable_mappings']}")
    print(f"  field-code values: {result['field_code_values_redacted']} redacted")
    print(f"  image assets     : {result['image_assets_redacted']} redacted")
    print(f"  elapsed          : {elapsed:.1f}s")
    print("  by type:")
    for entity_type, count in result["by_type"].items():
        print(f"    {entity_type:<15} {count}")
    print(f"  mapping    -> {mapping_path}")
    print(f"  detections -> {detections_path}")
    print(f"  field code -> {field_code_path}")
    print(f"  media      -> {media_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
