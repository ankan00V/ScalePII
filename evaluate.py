#!/usr/bin/env python3
"""Score the detector against the hand-labelled gold standard.

    python evaluate.py

Writes reports/evaluation.json and prints the tables that go into
EVALUATION.md.

What is measured, and why three different numbers
-------------------------------------------------
**Strict span P/R/F1** — a hit only counts if the predicted span's boundaries
and type match the gold span exactly. This is the honest number for "did the
detector understand the entity", and it punishes boundary drift such as
catching "Harbor & Co. LLP," with the trailing comma.

**Relaxed span P/R/F1** — a hit counts if the spans overlap and the type
matches. This is the number that reflects *redaction risk*, which is what
actually matters for this task: if I replace a superset of the PII, the PII is
still gone. A strict-only report would overstate the privacy risk, and a
relaxed-only report would hide sloppy boundaries. Both are reported.

**Character-level accuracy** — every character in the evaluated blocks is
classified PII / not-PII. This is the only one of the three that has a
meaningful true-negative count, which is what "accuracy" requires; span
metrics have no TN to speak of. It is reported for completeness because the
brief asks for accuracy, but note that it is dominated by the ~98% of
characters that are not PII, so it is high almost by construction and is the
least informative of the three.
"""

from __future__ import annotations

import json
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from piiredact.docx_io import load_blocks  # noqa: E402
from piiredact.pipeline import detect_only  # noqa: E402
from redact import load_nlp  # noqa: E402

ENTITY_TYPES = ["PERSON", "ORG", "EMAIL", "PHONE", "ADDRESS", "DIN", "WEBSITE"]


def _audit_reference(block: str, entity_type: str, text: str) -> dict[str, object]:
    """Describe an evaluation error without copying source PII into reports."""
    return {
        "block": block,
        "type": entity_type,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "length": len(text),
    }


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "support": tp + fn,
    }


def score_spans(pairs, strict: bool) -> tuple[dict, list, list]:
    """Match predictions to gold, one-to-one, greedily.

    ``pairs`` is a sequence of ``(gold_entities, predicted_spans)`` per block.
    Greedy one-to-one matching prevents a single sprawling prediction from
    claiming credit for several gold entities at once.
    """
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    false_positives, false_negatives = [], []

    for block_id, gold, predicted in pairs:
        unmatched_pred = list(predicted)
        for entity in gold:
            match = None
            for candidate in unmatched_pred:
                if candidate.entity_type != entity["entity_type"]:
                    continue
                if strict:
                    hit = (
                        candidate.start == entity["start"]
                        and candidate.end == entity["end"]
                    )
                else:
                    hit = (
                        candidate.start < entity["end"]
                        and entity["start"] < candidate.end
                    )
                if hit:
                    match = candidate
                    break
            if match is not None:
                unmatched_pred.remove(match)
                counts[entity["entity_type"]]["tp"] += 1
            else:
                counts[entity["entity_type"]]["fn"] += 1
                false_negatives.append(
                    _audit_reference(block_id, entity["entity_type"], entity["text"])
                )
        for leftover in unmatched_pred:
            counts[leftover.entity_type]["fp"] += 1
            false_positives.append(
                _audit_reference(block_id, leftover.entity_type, leftover.text)
            )

    report = {
        entity_type: _prf(**counts[entity_type])
        for entity_type in ENTITY_TYPES
        if counts[entity_type]["tp"] or counts[entity_type]["fp"] or counts[entity_type]["fn"]
    }
    total_tp = sum(c["tp"] for c in counts.values())
    total_fp = sum(c["fp"] for c in counts.values())
    total_fn = sum(c["fn"] for c in counts.values())
    report["MICRO_AVG"] = _prf(total_tp, total_fp, total_fn)
    scored = [v for k, v in report.items() if k != "MICRO_AVG"]
    if scored:
        # A stratum can legitimately contain no entities and no predictions —
        # that is the point of the body stratum — so guard the average.
        report["MACRO_AVG"] = {
            "precision": round(sum(v["precision"] for v in scored) / len(scored), 4),
            "recall": round(sum(v["recall"] for v in scored) / len(scored), 4),
            "f1": round(sum(v["f1"] for v in scored) / len(scored), 4),
        }
    return report, false_positives, false_negatives


def score_characters(pairs) -> dict:
    """Character-level PII / not-PII confusion matrix."""
    tp = fp = fn = tn = 0
    for _block_id, gold, predicted, text in pairs:
        gold_mask = bytearray(len(text))
        pred_mask = bytearray(len(text))
        for entity in gold:
            for i in range(entity["start"], min(entity["end"], len(text))):
                gold_mask[i] = 1
        for span in predicted:
            for i in range(span.start, min(span.end, len(text))):
                pred_mask[i] = 1
        for g, p in zip(gold_mask, pred_mask):
            if g and p:
                tp += 1
            elif p and not g:
                fp += 1
            elif g and not p:
                fn += 1
            else:
                tn += 1
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp_chars": tp,
        "fp_chars": fp,
        "fn_chars": fn,
        "tn_chars": tn,
        "accuracy": round((tp + tn) / total, 6) if total else 0.0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(
            2 * precision * recall / (precision + recall) if precision + recall else 0.0, 4
        ),
    }


def _table(title: str, report: dict) -> str:
    lines = [
        f"### {title}",
        "",
        "| Entity type | Support | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in report.items():
        if name == "MACRO_AVG":
            continue
        label = f"**{name}**" if name == "MICRO_AVG" else name
        lines.append(
            f"| {label} | {row['support']} | {row['tp']} | {row['fp']} | {row['fn']} "
            f"| {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |"
        )
    macro = report.get("MACRO_AVG")
    if macro:
        lines.append(
            f"| **MACRO_AVG** | | | | | {macro['precision']:.3f} "
            f"| {macro['recall']:.3f} | {macro['f1']:.3f} |"
        )
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default="gold/gold_standard.jsonl")
    parser.add_argument("--out", default="reports/evaluation.json")
    parser.add_argument("--label", default="dev")
    args = parser.parse_args()

    gold_path = Path(args.gold)
    if not gold_path.exists():
        raise SystemExit("run build_gold_sample.py then build_gold.py first")
    gold_rows = [json.loads(line) for line in gold_path.open(encoding="utf-8")]
    gold_by_index = {row["block_index"]: row for row in gold_rows}

    document, blocks = load_blocks("input.docx")
    nlp = load_nlp()
    # Detection runs over the *whole* document, exactly as in a redaction run,
    # then is sliced down to the sampled blocks. Running it only on the sample
    # would deprive the gazetteer of the rest of the document and measure a
    # pipeline that does not exist.
    predictions = detect_only(blocks, nlp=nlp, document=document)

    span_pairs, char_pairs = [], []
    per_stratum = defaultdict(list)
    for index, row in gold_by_index.items():
        predicted = predictions[index]
        block_id = row["block_id"]
        span_pairs.append((block_id, row["entities"], predicted))
        char_pairs.append((block_id, row["entities"], predicted, row["text"]))
        per_stratum[row["stratum"]].append((block_id, row["entities"], predicted))

    strict, strict_fp, strict_fn = score_spans(span_pairs, strict=True)
    relaxed, relaxed_fp, relaxed_fn = score_spans(span_pairs, strict=False)
    characters = score_characters(char_pairs)

    stratum_reports = {
        name: score_spans(pairs, strict=False)[0] for name, pairs in per_stratum.items()
    }

    result = {
        "blocks_evaluated": len(gold_rows),
        "gold_entities": sum(len(r["entities"]) for r in gold_rows),
        "strict_span": strict,
        "relaxed_span": relaxed,
        "character_level": characters,
        "by_stratum_relaxed": stratum_reports,
        "false_positives": relaxed_fp,
        "false_negatives": relaxed_fn,
    }
    result["split"] = args.label
    Path("reports").mkdir(exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"Split            : {args.label}")
    print(f"Blocks evaluated : {len(gold_rows)}")
    print(f"Gold entities    : {result['gold_entities']}\n")
    print(_table("Relaxed span match (overlap + type) — redaction-risk view", relaxed))
    print()
    print(_table("Strict span match (exact boundaries + type)", strict))
    print()
    print("### Character level")
    for key, value in characters.items():
        print(f"  {key:<12} {value}")
    print("\n### Relaxed micro-average by stratum")
    for name, report in stratum_reports.items():
        micro = report["MICRO_AVG"]
        print(
            f"  {name:<14} P={micro['precision']:.3f} R={micro['recall']:.3f} "
            f"F1={micro['f1']:.3f}  (support {micro['support']})"
        )
    if relaxed_fn:
        print("\n### False negatives (relaxed)")
        for item in relaxed_fn:
            print(
                f"  [{item['type']}] block={item['block']} "
                f"sha256={item['source_sha256'][:12]} length={item['length']}"
            )
    if relaxed_fp:
        print("\n### False positives (relaxed)")
        for item in relaxed_fp:
            print(
                f"  [{item['type']}] block={item['block']} "
                f"sha256={item['source_sha256'][:12]} length={item['length']}"
            )
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
