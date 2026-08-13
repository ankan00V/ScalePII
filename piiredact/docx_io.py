"""Reading and rewriting .docx text without destroying formatting.

The problem this module exists to solve
---------------------------------------
Word does not store a paragraph as a string. It stores a sequence of *runs*,
each carrying its own formatting, and it splits them at arbitrary points —
spell-check state, revision history, and font changes all cause splits. In
the prospectus I was given, paragraphs average **39.6 runs** and the worst
one has **319**. A single email address lands in the XML like this::

    ['E-mail:', ' ', '', '', '', 'contact@acme.example.org', '', ';', ...]

and an address or a person's name is routinely split mid-word.

So the naive approach — regex over ``run.text``, one run at a time — silently
misses every entity that straddles a run boundary. That is a *recall* bug
that never raises an error and never shows up in the output as anything but
un-redacted PII.

The approach here
-----------------
1. Concatenate the runs into the paragraph's real text, recording the
   character interval each run occupies.
2. Hand that flat string to the detectors.
3. Map each detected span back onto the runs it covers, and edit those runs
   in place.

The first run of a span receives the whole replacement; the remaining covered
runs have their overlapped slice deleted. Because we only ever touch the
*text* of a run and never its properties, bold/italic/font/size all survive.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterator

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .spans import Span, resolve_overlaps


@dataclass(slots=True)
class TextBlock:
    """One paragraph, flattened to a string plus the runs that back it."""

    text: str
    #: ``(start, end, run)`` for each backing run, in document order.
    layout: list[tuple[int, int, object]]
    #: Where this block came from, e.g. ``"body"`` / ``"header:3"``. Used to
    #: give evaluation samples a stable, quotable address.
    location: str
    index: int

    @property
    def block_id(self) -> str:
        return f"{self.location}#{self.index}"


def _owned_runs(p_element) -> list:
    """Every run belonging to this paragraph, including inside hyperlinks.

    ``Paragraph.runs`` skips runs nested in ``w:hyperlink``, which would
    desynchronise our offsets from the text we detect on. We walk the XML
    instead, and drop any run that actually belongs to a *nested* paragraph
    (text boxes embed whole paragraphs inside a run) — those are visited on
    their own turn, so counting them here would process them twice.
    """
    runs = []
    for r in p_element.iter(qn("w:r")):
        ancestor = r.getparent()
        while ancestor is not None and ancestor.tag != qn("w:p"):
            ancestor = ancestor.getparent()
        if ancestor is p_element:
            runs.append(r)
    return runs


def _iter_paragraph_elements(part_element) -> Iterator[object]:
    """Yield every ``w:p`` in a part, in document order.

    One flat walk covers body text, table cells at any nesting depth, and
    text boxes — no separate recursion for tables. This matters here: the
    highest-value PII in the document (the board table, with each director's
    name, DIN and *home address* on one row) lives in table cells, and much
    of the rest sits in the front-matter tables.
    """
    yield from part_element.iter(qn("w:p"))


def load_blocks(path: str) -> tuple[Document, list[TextBlock]]:
    """Open a .docx and flatten every paragraph it contains, anywhere."""
    document = Document(path)
    blocks: list[TextBlock] = []

    def harvest(part_element, location: str) -> None:
        for p_element in _iter_paragraph_elements(part_element):
            paragraph = Paragraph(p_element, None)
            runs = [
                run
                for run in (
                    _RunProxy(r, paragraph) for r in _owned_runs(p_element)
                )
            ]
            if not runs:
                continue
            layout: list[tuple[int, int, object]] = []
            cursor = 0
            pieces = []
            for run in runs:
                content = run.text
                layout.append((cursor, cursor + len(content), run))
                pieces.append(content)
                cursor += len(content)
            text = "".join(pieces)
            if not text.strip():
                continue
            blocks.append(
                TextBlock(text=text, layout=layout, location=location, index=len(blocks))
            )

    harvest(document.element.body, "body")
    # Headers and footers are separate XML parts and are easy to forget; a
    # running header repeating the issuer's name would leak straight through.
    # Multi-section documents commonly link later sections to the same
    # header/footer XML part. Process each part only once: reprocessing it
    # would redact a fake again and inflate the audit trail.
    seen_header_footer_parts: set[int] = set()
    for i, section in enumerate(document.sections):
        for label, part in (
            ("header", section.header),
            ("footer", section.footer),
            ("first_page_header", section.first_page_header),
            ("first_page_footer", section.first_page_footer),
            ("even_page_header", section.even_page_header),
            ("even_page_footer", section.even_page_footer),
        ):
            try:
                element = part._element
            except AttributeError:
                continue
            if element is None:
                continue
            identity = id(element)
            if identity in seen_header_footer_parts:
                continue
            seen_header_footer_parts.add(identity)
            harvest(element, f"{label}:{i}")

    return document, blocks


class _RunProxy:
    """Thin wrapper giving XML run elements a text get/set interface.

    python-docx's ``Run.text`` setter already re-encodes ``\\t`` and ``\\n``
    into ``w:tab`` / ``w:br``, so round-tripping a run that contained a tab
    does not lose it.
    """

    __slots__ = ("_r", "_run")

    def __init__(self, r_element, paragraph):
        from docx.text.run import Run

        self._r = r_element
        self._run = Run(r_element, paragraph)

    @property
    def text(self) -> str:
        return self._run.text

    @text.setter
    def text(self, value: str) -> None:
        self._run.text = value


def apply_to_block(block: TextBlock, replacements: list[tuple[Span, str]]) -> None:
    """Write ``replacements`` back into the runs behind ``block``.

    Edits are collected per run and applied right-to-left within each run, so
    two entities landing in the same run cannot invalidate each other's
    offsets.
    """
    if not replacements:
        return

    # run index -> list of (rel_start, rel_end, replacement)
    per_run: dict[int, list[tuple[int, int, str]]] = {}

    for span, fake in replacements:
        covered = [
            (i, start, end, run)
            for i, (start, end, run) in enumerate(block.layout)
            if start < span.end and span.start < end
        ]
        if not covered:
            continue
        for position, (i, start, end, _run) in enumerate(covered):
            rel_start = max(span.start - start, 0)
            rel_end = min(span.end - start, end - start)
            # The whole replacement goes into the first run of the span; the
            # rest simply lose their slice. This keeps the replacement under
            # one consistent format rather than splitting it across the
            # formatting of runs that happened to divide the original.
            payload = fake if position == 0 else ""
            per_run.setdefault(i, []).append((rel_start, rel_end, payload))

    for run_index, edits in per_run.items():
        run = block.layout[run_index][2]
        text = run.text
        for rel_start, rel_end, payload in sorted(edits, reverse=True):
            text = text[:rel_start] + payload + text[rel_end:]
        run.text = text


_FIELD_INSTRUCTION_TAGS = {qn("w:instrText"), qn("w:delInstrText")}


def redact_field_instructions(document, detectors, factory) -> list[dict[str, object]]:
    """Redact PII embedded in Word field instructions, such as hyperlinks.

    A visible mail address can be changed while the underlying ``HYPERLINK``
    field still stores the real ``mailto:`` value in ``w:instrText``. Word does
    not expose that instruction as a paragraph run, so the regular run-based
    pass cannot see it. Iterate every XML package part directly and apply the
    same detectors and stable fake mapping to those hidden instruction strings.

    The audit intentionally includes only a source hash, replacement, package
    part and field type. Storing the original instruction would re-introduce
    the PII this pass removes.
    """
    redactions: list[dict[str, object]] = []
    seen_part_names: set[str] = set()

    for part in document.part.package.parts:
        part_name = str(part.partname)
        if part_name in seen_part_names:
            continue
        seen_part_names.add(part_name)
        root = getattr(part, "element", None)
        if root is None:
            continue

        for element in root.iter():
            if element.tag not in _FIELD_INSTRUCTION_TAGS:
                continue
            original = element.text or ""
            if not original:
                continue

            candidates: list[Span] = []
            for detector in detectors:
                candidates.extend(detector.find(original))
            spans = resolve_overlaps(candidates)
            if not spans:
                continue

            replacement_text = original
            for span in reversed(spans):
                fake = factory.fake_for(span.entity_type, span.text)
                replacement_text = (
                    replacement_text[: span.start] + fake + replacement_text[span.end :]
                )
                redactions.append(
                    {
                        "part": part_name,
                        "field": "instruction",
                        "entity_type": span.entity_type,
                        "source_sha256": hashlib.sha256(
                            span.text.encode("utf-8")
                        ).hexdigest(),
                        "replacement": fake,
                    }
                )
            element.text = replacement_text

    return redactions
