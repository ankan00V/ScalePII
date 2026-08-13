# Evaluation Report

This report records current-code results reproduced from preserved assignment
inputs. The submission archive intentionally omits raw prospectus and
annotation files; the assignment recipient already has the former, and neither
is required to inspect the deliverable. I report the scores as evidence on these
saved annotations, not as a blind real-world generalisation estimate.

## Method

I evaluated the current detector against three saved annotation sets. The sets
are disjoint and are sampled by document position rather than detector output.
That avoids the circular mistake of evaluating only where the tool already
fired. Their saved sample files, labels and build commands reproduce exactly:

| Set | Blocks | Labelled entities | Sampling design | Seed |
|---|---:|---:|---|---:|
| Development v1 | 130 | 32 | 45 front matter, 40 body, 45 governance | 42 |
| Secondary v1 | 130 | 34 | Same v1 strata; excludes development blocks | 7 |
| Coverage v2 | 200 | 31 | 25 front matter, 150 middle, 25 governance; excludes both v1 sets | 2024 |

The working annotation tables live in `gold/*_annotations.py`; `build_gold.py`
resolves their surface strings to offsets mechanically. I verified that every
label appears in the sampled source block and that the saved gold JSONL files
rebuild byte-for-byte. The datasets do **not** provide inter-annotator
agreement, so the scores are best read as a reproducible engineering evaluation
rather than independent benchmark evidence.

The evaluator uses greedy, one-to-one matching of type-compatible spans.

| Metric | Rule | Meaning |
|---|---|---|
| Strict span precision/recall/F1 | Exact start, end and type | Measures boundary quality as well as detection. |
| Relaxed span precision/recall/F1 | Any overlap with the same type | Measures redaction coverage when a conservative span replaces a superset of the value. |
| Character accuracy | Per-character PII / non-PII classification | Supplies the requested accuracy; it is dominated by non-PII characters and must not be read alone. |

The span metrics cover the document text layer. Hidden Word hyperlink fields
and embedded images are validated separately in `verify_delivery.py`.

## Reproducing the samples and scores

The following commands are retained for the assignment recipient, who already
has the supplied prospectus and evaluation inputs. I exclude those raw-PII
inputs from the submission archive; the archive includes the current reports
and methodology instead.

```bash
python build_gold_sample.py --seed 42 --design v1 --out /tmp/dev.jsonl
python build_gold_sample.py --seed 7 --design v1 \
  --exclude gold/sample_to_label.jsonl --out /tmp/secondary.jsonl
python build_gold_sample.py --seed 2024 --design v2 \
  --exclude gold/sample_to_label.jsonl,gold/heldout_to_label.jsonl \
  --out /tmp/coverage.jsonl

python build_gold.py --sample gold/sample_to_label.jsonl \
  --annotations gold.annotations --out /tmp/dev-gold.jsonl
python evaluate.py --gold gold/gold_standard.jsonl \
  --out reports/evaluation.json --label development-current
python evaluate.py --gold gold/heldout_standard.jsonl \
  --out reports/evaluation_heldout.json --label secondary-current
python evaluate.py --gold gold/coverage_standard.jsonl \
  --out reports/evaluation_coverage.json --label coverage-current
```

## Current results

| Set | Relaxed precision | Relaxed recall | Relaxed F1 | Strict F1 | Character accuracy |
|---|---:|---:|---:|---:|---:|
| Development v1 | 1.000 | 1.000 | 1.000 | 0.969 | 0.9973 |
| Secondary v1 | **0.971** | **1.000** | **0.986** | **0.927** | **0.9944** |
| Coverage v2 | 1.000 | 1.000 | 1.000 | 0.935 | 0.9987 |

For the secondary v1 sample—the most useful separate sample in this package—
the relaxed confusion counts are 34 true positives, 1 false positive and 0
false negatives. The lone extra ORG span is preserved in
`reports/evaluation_heldout.json` as a hash-only audit reference. Strict F1 is
lower because it counts boundary differences: 32 exact matches, 3 extra spans
and 2 boundary misses. This distinction is intentional: an over-inclusive
address replacement may be safe for redaction but is still an imprecise span.

The single relaxed extra span is a named-company landmark inside an address. I
labelled that landmark out of scope in this annotation set, while the detector
redacts it. Because the assignment explicitly lists company names, a reviewer
may reasonably prefer the detector's more conservative behaviour; I keep the
annotation and its precision cost rather than changing a label to improve the
score.

## Whole-document run and verification

The current run has the following mechanically verified results:

| Check | Result |
|---|---:|
| Text blocks scanned | 4,181 |
| Visible-text replacements | 610 |
| Stable source-to-fake mappings | 258 |
| Hidden hyperlink field values redacted | 77 |
| Embedded image parts neutralised | 8 |
| Unit/integration tests | 40 passed |

`python verify_delivery.py` opens the final DOCX package and proves that it is
valid; preserves 1,006 paragraphs, 76 tables, 85 sections, 4,181 text blocks
and 4,193 bold runs; replaces all 8 embedded image payloads with neutral
placeholders; and leaves no source value detected by the current pipeline in
the serialized XML. It checks all 610 visible occurrences, 77 hidden field
occurrences and 27 source email values without writing those values to its
output. It also verifies that the generated audit artefacts use hashes rather
than cleartext source values.

## Scope and limitations

I redact people, company/legal-entity names, emails, phones, postal addresses,
DINs and non-allowlisted websites in this prospectus. The text scan produced no
SSN, credit-card, date-of-birth or IP-address matches; the implementation is
covered by an end-to-end synthetic test for each assignment-required type.
Regulators, statutes, exchanges and depositories are deliberately allowlisted;
this is a documented policy choice, not a claim that every organisation is safe
to retain. Every raster image is replaced rather than OCR-redacted, sacrificing
image utility for a fail-closed privacy policy.

No finite sample or automated scan proves that a document contains no missed
PII. The reported recall numbers describe these saved annotations only. The
verification script proves absence of *currently detected* source values from
the final package; it does not establish recall for values the detector never
identified. Historical `*_blind.json` files are retained as legacy artefacts
but are not used to support any claim in this report.
