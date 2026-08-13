"""The two-pass redaction pipeline.

Pass 1 (harvest) reads the whole document and builds gazetteers: which people,
organisations and DINs actually exist in *this* document. Pass 2 (apply) runs
the full detector set — now including those gazetteers — and rewrites the
runs.

Splitting it this way is what lifts recall on the open-class types. spaCy
tags a name confidently in prose and then misses it in a bare table cell that
contains nothing but the name; the harvest pass turns a single confident
detection anywhere into deterministic coverage everywhere.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .allowlist import (
    DOMAIN_NOISE,
    GENERIC_ENTITY_TOKENS,
    has_legal_entity_marker,
    is_allowlisted_org,
    is_only_generic,
    is_person_noise,
    is_redactable_org,
    load_glossary,
)
from .detectors import build_detectors
from .docx_io import (
    TextBlock,
    apply_to_block,
    load_blocks,
    redact_field_instructions,
)
from .fakes import FakeFactory, RedactionLedger
from .media import redact_embedded_images
from .spans import Span, resolve_overlaps

# High-precision cues that name a person outright. Anything matched here is
# trusted into the gazetteer without the model needing to agree.
_PERSON_CUES = (
    re.compile(r"(?i)\bcontact\s+person\s*[:\-]\s*([^\n;]+)"),
    re.compile(r"(?i)\bour\s+promoters?\s*[:\-]\s*([^\n]+)"),
    re.compile(r"(?i)\bcompliance\s+officer\s*[:\-]\s*([^\n;]+)"),
    # "…the independent chartered engineer appointed by our Company, namely,
    # Rohan Mehta bearing registration number M-123456". The
    # prospectus introduces named experts this way, and spaCy misses them.
    # Deliberately case-sensitive: under re.I the [A-Z] classes would also
    # match lowercase, so the capture ran on into "… Sarvaiya bearing" and
    # was then rejected for containing a non-name token.
    re.compile(r"\bnamely,?\s+((?:[A-Z][\w.'’\-]*\s+){1,3}[A-Z][\w.'’\-]*)"),
    re.compile(r"\bconsent\s+dated\s+[\w\s,]+?\s+from\s+((?:[A-Z][\w.'’\-]*\s+){1,3}[A-Z][\w.'’\-]*)"),
    re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Shri|Smt)\.?\s+((?:[A-Z][\w.'’\-]*\s+){0,3}[A-Z][\w.'’\-]*)"),
)
_DIN_CUE = re.compile(r"(?i)\bDIN\b\s*(?:no\.?|number)?\s*[:.\-]?\s*(\d{6,8})")
# Case-insensitive: the promoter roll is set in capitals, so a case-sensitive
# "and" would leave "SUMMIT FAMILY TRUST AND NORTHPOINT ..." as one chunk.
_SPLIT_LIST = re.compile(r",|\band\b|/|;", re.IGNORECASE)


@dataclass
class Gazetteers:
    persons: set[str] = field(default_factory=set)
    orgs: set[str] = field(default_factory=set)
    dins: set[str] = field(default_factory=set)

    def summary(self) -> dict[str, int]:
        return {
            "persons": len(self.persons),
            "orgs": len(self.orgs),
            "dins": len(self.dins),
        }


def _clean_candidate(value: str) -> str:
    # Footnote markers ride along on names in the tables — "Maya Patel^&",
    # "Arjun Mehta*^&" — and would otherwise mint a
    # separate fake for each decorated variant of the same person.
    value = value.strip(" \t.,;:-–—()[]*^&#†‡§¶~")
    value = re.sub(r"\s+", " ", value)
    # Drop a trailing role that ran on after the name, e.g.
    # "Dev Mehra, Company Secretary and Compliance Officer".
    value = re.sub(
        r"(?i)\b(?:company secretary|compliance officer|managing director"
        r"|joint managing director|executive director|independent director"
        r"|whole[- ]time director|chairman|director|chief financial officer)\b.*$",
        "",
        value,
    ).strip(" ,;-")
    return value


def _looks_like_person(value: str) -> bool:
    if is_person_noise(value, strict=True):
        return False
    tokens = value.split()
    if not 2 <= len(tokens) <= 5:
        return False
    # Require every token to look like a name token (letters, initial caps in
    # either title or upper case).
    return all(re.fullmatch(r"[A-Za-z][A-Za-z'.\-]*", t) for t in tokens)


def harvest_glossary(document) -> set[str]:
    """Collect the headwords of the prospectus's own definitions tables.

    A red herring prospectus opens with "DEFINITIONS AND ABBREVIATIONS": a
    long sequence of two-column ``Term | Description`` tables. Those
    headwords are precisely the capitalised phrases that spaCy mistakes for
    entities — "Bid Amount", "Anchor Investor", "Key Managerial Personnel".

    Harvesting them turns the document's own controlled vocabulary into a
    tailored allowlist, which is far more accurate than any list I could
    hand-write, and it adapts automatically to a different prospectus.
    """
    terms: set[str] = set()
    for table in document.tables:
        if len(table.columns) != 2 or not table.rows:
            continue
        header = [cell.text.strip().lower() for cell in table.rows[0].cells]
        is_glossary = header[0] in {"term", "terms"} or (
            len(header) > 1 and header[1].startswith("descri")
        )
        if not is_glossary:
            continue
        for row in table.rows[1:]:
            headword = re.sub(r"\s+", " ", row.cells[0].text).strip()
            if 2 < len(headword) < 90:
                terms.add(headword)
    return terms


def harvest_name_columns(document) -> tuple[set[str], set[str]]:
    """Harvest people and entities from any table column headed "Name".

    The board of directors is laid out as ``Name | Designation | DIN |
    Address``, one director per row. Relying on the NER model to read those
    cells fails: a cell containing only "Dinesh Hirachand Munot" has no
    sentence context, and the model returns nothing — so an independent
    director's name, DIN and home address were surviving redaction intact.

    Reading the column directly is both more accurate and more honest about
    what the document actually is. Values are still routed through the same
    person/organisation tests, so a "Name of entity" column yields
    organisations and a directors' column yields people, without either
    needing to be declared up front.
    """
    persons: set[str] = set()
    orgs: set[str] = set()
    for table in document.tables:
        if not table.rows:
            continue
        headers = [cell.text.strip().lower() for cell in table.rows[0].cells]
        name_columns = [
            i
            for i, header in enumerate(headers)
            if header == "name" or header.startswith("name of")
        ]
        if not name_columns:
            continue
        for row in table.rows[1:]:
            cells = row.cells
            for column in name_columns:
                if column >= len(cells):
                    continue
                value = _clean_candidate(re.sub(r"\s+", " ", cells[column].text))
                if not value or len(value) > 80:
                    continue
                if _looks_like_person(value):
                    persons.add(value)
                elif has_legal_entity_marker(value):
                    orgs.add(value)
    return persons, orgs


def _base_entity_names(orgs: set[str]) -> set[str]:
    """Strip corporate suffixes to catch shorthand references.

    The document introduces "Acme Metals Limited" and then refers to
    "Acme Metals"; likewise "Northpoint Industrial Park VI Private
    Limited" appears once as plain "Northpoint Industrial Park". Matching only
    the full legal name leaves those shorthand mentions in the clear, which
    defeats the point of redacting the name at all.

    Guarded so that stripping never produces something generic: "Bank
    Limited" would reduce to "Bank", which must not become a match term.
    """
    bases: set[str] = set()
    suffix = re.compile(
        r"(?i)[\s,]*(?:\b(?:Private|Public|Pvt\.?)\b[\s,]*)?"
        r"\b(?:Limited|Ltd\.?|LLP|LLC|Inc\.?|Corporation|Corp\.?|GmbH|PLC|Trust|HUF)\b"
        r"[\s.,]*$"
    )
    roman = re.compile(r"(?i)[\s,]*\b(?:I{1,3}|IV|V|VI{1,3}|IX|XI{0,3})\b[\s,]*$")
    for org in orgs:
        base = suffix.sub("", org).strip()
        for candidate in (base, roman.sub("", base).strip()):
            tokens = candidate.split()
            if len(tokens) < 2 or candidate.lower() == org.lower():
                continue
            if is_only_generic(candidate) or is_allowlisted_org(candidate):
                continue
            if all(token.lower() in GENERIC_ENTITY_TOKENS for token in tokens[1:]):
                continue
            bases.add(candidate)
    return bases


def _family_names(persons: set[str]) -> set[str]:
    """Surnames of the promoter individuals.

    Promoter families name their group entities after themselves — "Alder
    Electricals", "Morgan HUF". Those carry no corporate suffix, so
    the surname is the only signal that they are promoter-linked and in scope.

    The generic-token guard matters more than it looks: a trailing conjunction
    or corporate form leaking in here ("... FAMILY TRUST AND") would install
    "and" or "trust" as a surname, and every phrase in the document
    containing that word would then be redacted as a promoter entity.
    """
    surnames = set()
    for person in persons:
        tokens = [t for t in person.split() if len(t) > 2]
        if len(tokens) < 2:
            continue
        surname = tokens[-1]
        if len(surname) < 4:
            continue
        if surname.lower() in GENERIC_ENTITY_TOKENS or surname.lower() in DOMAIN_NOISE:
            continue
        surnames.add(surname)
    return surnames


def harvest(
    blocks: list[TextBlock], nlp, document=None
) -> tuple[Gazetteers, list[list[tuple[int, str, str]]]]:
    """Pass 1. Returns the gazetteers plus cached NER output per block."""
    gazetteers = Gazetteers()
    cached_ents: list[list[tuple[int, str, str]]] = []

    texts = [block.text for block in blocks]
    if nlp is not None:
        # Only the NER components are needed; disabling the rest roughly
        # halves the runtime on a 446k-character document.
        docs = nlp.pipe(texts, batch_size=64)
    else:
        docs = (None for _ in texts)

    org_candidates: set[str] = set()
    promoters: set[str] = set()

    # Structural harvest first: table columns are more reliable than the
    # model on exactly the rows that matter most.
    if document is not None:
        table_persons, table_orgs = harvest_name_columns(document)
        gazetteers.persons |= table_persons
        org_candidates |= table_orgs

    for text, doc in zip(texts, docs):
        ents = (
            [(e.start_char, e.text, e.label_) for e in doc.ents] if doc is not None else []
        )
        cached_ents.append(ents)

        # Route raw NER output ourselves rather than through the filtered
        # detectors. The model's PERSON/ORG boundary is unreliable on
        # corporate promoters — it tags "Northpoint Industrial Park VI Private
        # Limited" as a PERSON — so a candidate rejected as a person must
        # still get a hearing as an organisation.
        for _offset, raw, label in ents:
            candidate = _clean_candidate(raw)
            if not candidate:
                continue
            if label == "PERSON":
                if _looks_like_person(candidate):
                    gazetteers.persons.add(candidate)
                elif has_legal_entity_marker(candidate):
                    org_candidates.add(candidate)
            elif label == "ORG":
                org_candidates.add(candidate)

        # High-precision cues are trusted without the model's agreement, and
        # they are the reason the contact persons and promoters are caught
        # even where they appear only inside a cramped table cell.
        for cue_index, cue in enumerate(_PERSON_CUES):
            for match in cue.finditer(text):
                for part in _SPLIT_LIST.split(match.group(1)):
                    candidate = _clean_candidate(part)
                    if _looks_like_person(candidate):
                        gazetteers.persons.add(candidate)
                        if cue_index == 1:  # the "OUR PROMOTERS:" cue
                            promoters.add(candidate)
                    elif has_legal_entity_marker(candidate):
                        # A corporate promoter is redacted as an organisation,
                        # but must not seed the surname rule — its last token
                        # is a corporate form, not a family name.
                        org_candidates.add(candidate)

        for match in _DIN_CUE.finditer(text):
            gazetteers.dins.add(match.group(1))

    # Organisations are filtered only now, because the surname rule needs the
    # promoter list to be complete. Restricting it to *promoter* surnames —
    # rather than every person in the document — is deliberate: widening it
    # to all persons pulled in fragments like "Eric Bacha/" and
    # "Sancheti Hospital Shivajinagar".
    surnames = _family_names(promoters or gazetteers.persons)
    gazetteers.orgs = {
        candidate
        for candidate in org_candidates
        if is_redactable_org(candidate, surnames)
    }
    # Shorthand references ("Acme Metals" for "Acme Metals
    # Limited") only become matchable once the full names are settled.
    gazetteers.orgs |= _base_entity_names(gazetteers.orgs)

    # The board table lists name / designation / DIN / address in adjacent
    # cells with no "DIN" label anywhere. Any bare 8-digit number sitting in
    # a block whose neighbours are known directors is a DIN.
    gazetteers.dins |= _harvest_table_dins(blocks, gazetteers.persons)

    return gazetteers, cached_ents


def _harvest_table_dins(blocks: list[TextBlock], persons: set[str]) -> set[str]:
    """Recover unlabelled DINs from the board table by positional proximity."""
    found: set[str] = set()
    lowered_persons = {p.lower() for p in persons}
    for index, block in enumerate(blocks):
        stripped = block.text.strip()
        if not re.fullmatch(r"\d{8}", stripped):
            continue
        window = " ".join(
            b.text.lower() for b in blocks[max(0, index - 4) : index + 5]
        )
        if any(person in window for person in lowered_persons):
            found.add(stripped)
    return found


def redact(
    input_path: str,
    output_path: str,
    nlp=None,
    seed: int = 20251210,
    redact_images: bool = True,
) -> dict:
    """Run the full pipeline and write the redacted .docx."""
    document, blocks = load_blocks(input_path)
    # Install the document's own defined terms before anything is filtered.
    load_glossary(harvest_glossary(document))
    gazetteers, _ = harvest(blocks, nlp, document=document)

    # Pass 2 applies the gazetteers rather than re-running the model. Every
    # name the model found has already been promoted into a gazetteer (after
    # filtering), and the gazetteer then matches it in *every* block —
    # including the table cells the model cannot read. Re-running raw NER
    # here would only re-admit the candidates the filters just rejected.
    detectors = build_detectors(
        nlp=None,
        person_terms=gazetteers.persons,
        org_terms=gazetteers.orgs,
        known_dins=gazetteers.dins,
    )

    factory = FakeFactory(seed=seed)
    ledger = RedactionLedger()
    detections_log: list[dict] = []

    for block in blocks:
        candidates: list[Span] = []
        for detector in detectors:
            candidates.extend(detector.find(block.text))

        final = resolve_overlaps(candidates)
        if not final:
            continue

        replacements = []
        for span in final:
            fake = factory.fake_for(span.entity_type, span.text)
            replacements.append((span, fake))
            ledger.record(span.entity_type)
            detections_log.append(
                {
                    "start": span.start,
                    "end": span.end,
                    "length": len(span),
                    "entity_type": span.entity_type,
                    "detector": span.detector,
                    "block": block.block_id,
                    "source_sha256": hashlib.sha256(
                        span.text.encode("utf-8")
                    ).hexdigest(),
                    "replacement": fake,
                }
            )

        apply_to_block(block, replacements)
        ledger.blocks_touched += 1

    field_code_redactions = redact_field_instructions(document, detectors, factory)
    media_redactions = redact_embedded_images(document) if redact_images else []
    document.save(output_path)

    return {
        "blocks_scanned": len(blocks),
        "blocks_touched": ledger.blocks_touched,
        "replacements": ledger.replacements,
        "by_type": dict(sorted(ledger.by_type.items())),
        "gazetteers": gazetteers.summary(),
        "field_code_values_redacted": len(field_code_redactions),
        "field_code_redactions": field_code_redactions,
        "image_assets_redacted": len(media_redactions),
        "media_redactions": media_redactions,
        "mapping": factory.mapping_rows(),
        "detections": detections_log,
    }


def detect_only(
    blocks: list[TextBlock], nlp=None, document=None
) -> list[list[Span]]:
    """Run detection without rewriting anything.

    The evaluation harness uses this so that scoring measures exactly the
    same detector output that redaction would act on.
    """
    if document is not None:
        load_glossary(harvest_glossary(document))
    gazetteers, _ = harvest(blocks, nlp, document=document)
    detectors = build_detectors(
        nlp=None,
        person_terms=gazetteers.persons,
        org_terms=gazetteers.orgs,
        known_dins=gazetteers.dins,
    )
    results = []
    for block in blocks:
        candidates: list[Span] = []
        for detector in detectors:
            candidates.extend(detector.find(block.text))
        results.append(resolve_overlaps(candidates))
    return results
