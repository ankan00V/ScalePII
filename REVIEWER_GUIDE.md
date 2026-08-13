# Reviewer Guide

Thank you for reviewing my submission. I designed the handoff to be inspectable
quickly, while keeping the supplied raw prospectus out of the archive.

## Start here

1. Open `output/Red Herring Prospectus - REDACTED.docx` to review the requested
   output. It retains Word layout while replacing detected values with stable,
   plausible fakes.
2. Read `README.md` for the architecture and policy decisions.
3. Read `EVALUATION.md` for the reproducible metrics and their limitations.

## Fast technical check

The archived test suite is self-contained:

```bash
pip install -r requirements.txt
python -m unittest discover tests -v
```

To re-run against the prospectus supplied with the assignment, place it in the
archive root as `input.docx`, then run:

```bash
python redact.py --input input.docx --output "output/Red Herring Prospectus - REDACTED.docx"
python verify_delivery.py
```

`verify_delivery.py` is deliberately stronger than a text-only smoke test. It
checks the saved DOCX package for detected visible text, hidden hyperlink
targets and embedded image payloads, while ensuring paragraph/table/section
structure is preserved.

## What I would want a reviewer to notice

* The replacement layer is consistent and seeded, so repeated entities receive
  the same fake while presentation variants share a mapping.
* Detection is performed over flattened Word runs, avoiding missed values split
  across formatting or hyperlinks.
* The default image policy is fail-closed: all raster images are neutralised,
  not merely those identified by OCR.
* The reported scores are not presented as proof that all PII was found. The
  evaluation report distinguishes reproducible sample evidence from claims the
  repository cannot establish.

The supplied prospectus is deliberately not copied into this archive: it is raw
sensitive material the reviewer already has. The generated audit files contain
only source hashes and fake replacements, never cleartext source PII.
