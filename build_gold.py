#!/usr/bin/env python3
"""Resolve the hand-written labels in gold/annotations.py into offset spans.

Labelling by surface string and resolving offsets mechanically removes a
whole class of transcription error: I never type a character offset by hand,
so a gold span can never silently point at the wrong text.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="gold/sample_to_label.jsonl")
    parser.add_argument("--annotations", default="gold.annotations")
    parser.add_argument("--out", default="gold/gold_standard.jsonl")
    args = parser.parse_args()

    GOLD = importlib.import_module(args.annotations).GOLD
    sample_path = Path(args.sample)
    if not sample_path.exists():
        raise SystemExit("run build_gold_sample.py first")

    rows = [json.loads(line) for line in sample_path.open(encoding="utf-8")]
    known = {row["block_index"] for row in rows}
    unknown = set(GOLD) - known
    if unknown:
        raise SystemExit(f"annotations reference unsampled blocks: {sorted(unknown)}")

    total = 0
    out = Path(args.out)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            text = row["text"]
            entities = []
            for surface, entity_type in GOLD.get(row["block_index"], []):
                start = text.find(surface)
                if start == -1:
                    raise SystemExit(
                        f"block {row['block_index']}: label {surface!r} not found "
                        f"in block text"
                    )
                while start != -1:
                    entities.append(
                        {
                            "start": start,
                            "end": start + len(surface),
                            "text": surface,
                            "entity_type": entity_type,
                        }
                    )
                    start = text.find(surface, start + len(surface))
            entities.sort(key=lambda e: e["start"])
            total += len(entities)
            row["entities"] = entities
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"wrote {out}: {len(rows)} blocks, {total} labelled entities")
    by_type: dict[str, int] = {}
    for row in rows:
        for entity in row["entities"]:
            by_type[entity["entity_type"]] = by_type.get(entity["entity_type"], 0) + 1
    for entity_type, count in sorted(by_type.items()):
        print(f"  {entity_type:<12} {count}")


if __name__ == "__main__":
    main()
