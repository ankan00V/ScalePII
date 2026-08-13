#!/usr/bin/env python3
"""Draw a stratified sample for the gold-annotation workflow.

Sampling design
---------------
The sample is drawn by **document position only** — never by whether the
detector fired. Selecting blocks because something was detected there would
make recall circular: false negatives would be invisible by construction.

Three strata, chosen because PII is very unevenly distributed in a
prospectus:

  ``front_matter``  blocks 0-700     cover page, definitions, general
                                     information and capital structure.
  ``governance``    blocks 3550-3900 the board table and the second general
                                     information section: names, DINs and
                                     directors' home addresses.
  ``body``          everything else  risk factors, business, financial
                                     statements. Nearly PII-free, and so the
                                     stratum that exposes false positives.

Because the sample deliberately over-represents PII-dense regions, its pooled
metrics should be interpreted as a stratified-sample result, not a documentwide
prevalence estimate.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from piiredact.docx_io import load_blocks

SEED = 42

#: The original design. Good for the PII-dense regions, but it samples the
#: 2,850-block middle of the document at only 40 blocks.
STRATA_V1 = {
    "front_matter": (0, 700, 45),
    "governance": (3550, 3900, 45),
    "body": (None, None, 40),
}

#: Coverage-focused design. It puts the bulk of the sample in blocks 700-3550,
#: the business, litigation, promoter-group and financial-statement region.
#: Most drawn blocks may be empty; they are retained so that precision is not
#: measured only where an entity appears.
STRATA_V2 = {
    "front_matter": (0, 700, 25),
    "mid_document": (700, 3550, 150),
    "governance": (3550, 3900, 25),
}

DESIGNS = {"v1": STRATA_V1, "v2": STRATA_V2}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", default="gold/sample_to_label.jsonl")
    parser.add_argument("--design", choices=sorted(DESIGNS), default="v1")
    parser.add_argument(
        "--exclude",
        default=None,
        help="comma-separated sample .jsonl files whose blocks must not be "
        "drawn again; used to carve a held-out set disjoint from earlier ones",
    )
    args = parser.parse_args()
    strata = DESIGNS[args.design]

    _, blocks = load_blocks("input.docx")
    rng = random.Random(args.seed)

    already: set[int] = set()
    for path in filter(None, (args.exclude or "").split(",")):
        already |= {
            json.loads(line)["block_index"]
            for line in Path(path.strip()).open(encoding="utf-8")
        }

    reserved = set(range(0, 700)) | set(range(3550, 3900))
    chosen: list[tuple[str, int]] = []

    for name, (start, end, count) in strata.items():
        if start is None:
            pool = [
                i for i in range(len(blocks)) if i not in reserved and i not in already
            ]
        else:
            pool = [
                i for i in range(start, min(end, len(blocks))) if i not in already
            ]
        chosen.extend((name, i) for i in rng.sample(pool, min(count, len(pool))))

    chosen.sort(key=lambda pair: pair[1])

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for stratum, index in chosen:
            handle.write(
                json.dumps(
                    {
                        "block_index": index,
                        "stratum": stratum,
                        "block_id": blocks[index].block_id,
                        "text": blocks[index].text,
                        "entities": [],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"wrote {len(chosen)} blocks to {out}")
    for name in strata:
        print(f"  {name:<14} {sum(1 for s, _ in chosen if s == name)}")


if __name__ == "__main__":
    main()
