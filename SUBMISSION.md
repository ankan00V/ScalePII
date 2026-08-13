# Submission Manifest

I built `PII_Redaction_Submission.zip` with the following items:

1. `redact.py`, `piiredact/`, `assets/`, `requirements.txt` and
   `verify_delivery.py` — the implementation and verifier.
2. `tests/` — 40 regression and integration tests, including all required PII
   types, split Word runs, hidden hyperlink fields and embedded images.
3. `output/Red Herring Prospectus - REDACTED.docx` — the requested redacted
   Word deliverable.
4. `README.md`, `EVALUATION.md` and `REVIEWER_GUIDE.md` — the approach,
   trade-offs, metrics, evidence and a fast review path.
5. `reports/evaluation.json`, `reports/evaluation_heldout.json`,
   `reports/evaluation_coverage.json`, `reports/run_summary.json` and the
   privacy-safe files in `output/` — reproducible run evidence.

The supplied `input.docx` is raw sensitive material that the assignment
recipient already owns. I deliberately do not duplicate it in the archive.
The archived tests are synthetic and self-contained; a reviewer can copy the
provided prospectus into the archive root as `input.docx` to re-run the tool and
verifier. The `gold/` annotation data is also excluded because it repeats source
PII and is not an assignment deliverable.

`CONTEXT.md`, Python caches and legacy `reports/*_blind.json` files are excluded
because they are not part of the final evidence cited in the submission.
