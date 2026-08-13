"""One detector per PII type.

Design
------
Every detector implements the same two-member interface::

    class MyDetector(Detector):
        entity_type = "MY_TYPE"
        def find(self, text: str) -> list[Span]: ...

and is added to ``build_detectors()``. That is the whole extension story: to
support a new PII type I write one class here and one generator in
``fakes.py``. Nothing else in the pipeline changes, because everything
downstream only ever sees ``Span`` objects.

Why a hybrid of regex and NER, rather than one or the other
-----------------------------------------------------------
The PII in this document splits cleanly into two populations:

*Closed-form values* — email, phone, SSN, credit card, IP, DIN. These have a
rigid grammar. Regex gets essentially perfect precision *and* recall on them,
and a statistical model would only add non-determinism. Where a pattern is
ambiguous against the document's own content (a 10-digit number is a phone
number *or* a share count in a financial table) I gate on context rather than
loosening the pattern.

*Open-class values* — person, organisation, address. No grammar exists. Here
I use spaCy NER, but wrap it in two correctives: a gazetteer that promotes
recall, and an allowlist that protects precision.

The gazetteer is the important half. spaCy will reliably tag
"Arjun Mehta" in a well-formed sentence and then miss the same name
in a cramped table cell with no sentence context around it. So I run a first
pass purely to *harvest* entities, then match those harvested strings
literally across the whole document in the second pass. One confident
detection anywhere propagates to every occurrence everywhere.
"""

from __future__ import annotations

import re
from typing import Iterable, Protocol

from .allowlist import (
    is_allowlisted_org,
    is_defined_term,
    is_only_generic,
    is_person_noise,
)
from .spans import Span

# Priority bands. Deterministic beats statistical when they overlap.
P_STRUCTURED = 100
P_CONTEXTUAL = 80
P_GAZETTEER = 60
P_MODEL = 40


class Detector(Protocol):
    entity_type: str
    name: str

    def find(self, text: str) -> list[Span]: ...


class _RegexDetector:
    """Shared base for the closed-form detectors."""

    entity_type = "OVERRIDE"
    name = "regex"
    pattern: re.Pattern
    priority = P_STRUCTURED
    group = 0

    def find(self, text: str) -> list[Span]:
        spans = []
        for match in self.pattern.finditer(text):
            value = match.group(self.group)
            if not self.accept(value, text, match):
                continue
            spans.append(
                Span(
                    start=match.start(self.group),
                    end=match.end(self.group),
                    text=value,
                    entity_type=self.entity_type,
                    detector=self.name,
                    priority=self.priority,
                )
            )
        return spans

    def accept(self, value: str, text: str, match: re.Match) -> bool:  # noqa: ARG002
        return True


# --------------------------------------------------------------------------
# Closed-form detectors
# --------------------------------------------------------------------------


class EmailDetector(_RegexDetector):
    entity_type = "EMAIL"
    name = "regex:email"
    pattern = re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )


class WebsiteDetector(_RegexDetector):
    """URLs are redacted because they re-identify the organisation.

    ``www.acme.example.org`` names the issuer as surely as its company
    name does, so leaving it in would defeat the organisation redaction.
    Allowlisted institutional domains (the regulator's own site, the exchange)
    are kept, mirroring the organisation policy.
    """

    entity_type = "WEBSITE"
    name = "regex:website"
    pattern = re.compile(
        r"\b(?:https?://|www\.)[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+[A-Za-z0-9/]"
    )
    _KEEP = (
        "sebi.gov.in", "bseindia", "nseindia", "rbi.org.in", "mca.gov.in",
        "fbil.org.in", "nsdl", "cdsl", "oanda.com", "npci",
    )

    def accept(self, value: str, text: str, match: re.Match) -> bool:
        return not any(keep in value.lower() for keep in self._KEEP)


class IPAddressDetector(_RegexDetector):
    entity_type = "IP_ADDRESS"
    name = "regex:ip"
    pattern = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
    )

    def accept(self, value: str, text: str, match: re.Match) -> bool:
        # A version string ("Ind AS 115.2.3.1") and a section reference can
        # both look like an IPv4 address. Require it not to be adjacent to
        # more digits or a decimal continuation.
        tail = text[match.end() : match.end() + 2]
        return not tail.startswith(".")


class SSNDetector(_RegexDetector):
    entity_type = "SSN"
    name = "regex:ssn"
    # US SSN, incl. the ranges the SSA never issues.
    pattern = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")


class CreditCardDetector(_RegexDetector):
    entity_type = "CREDIT_CARD"
    name = "regex:credit_card"
    pattern = re.compile(r"\b(?:\d[ \-]?){12,18}\d\b")

    def accept(self, value: str, text: str, match: re.Match) -> bool:
        digits = re.sub(r"\D", "", value)
        if not 13 <= len(digits) <= 19:
            return False
        if digits[0] not in "3456":  # Amex/Visa/Mastercard/Discover
            return False
        return _luhn_ok(digits)


def _luhn_ok(digits: str) -> bool:
    """Luhn checksum.

    Without this, any 16-digit figure in a financial table is a 'credit
    card'. This document is full of long numbers; the checksum is what keeps
    the credit-card detector from being a precision disaster.
    """
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


class PhoneDetector:
    """Phone numbers, gated on either a ``+`` prefix or a nearby label.

    An ungated 10-digit pattern would match share counts, rupee amounts and
    page references throughout the financial statements. The document always
    presents real numbers either in international form or behind a label
    ("Telephone:", "Tel:", "Fax:", "Mobile:"), so I require one of those.
    """

    entity_type = "PHONE"
    name = "regex:phone"

    _INTERNATIONAL = re.compile(r"\+\s?\d{1,3}[\s\-]?\d[\d\s\-]{6,15}\d")
    _LABEL = re.compile(
        r"(?i)\b(?:tele?phone|tel|phone|mobile|fax|contact\s+no|helpline)\b"
        r"\s*(?:no\.?|number)?\s*[:.\-]?\s*"
    )
    _AFTER_LABEL = re.compile(r"(?:\+?\s?\d[\d\s\-()]{7,17}\d)")

    def find(self, text: str) -> list[Span]:
        spans: list[Span] = []
        seen: set[tuple[int, int]] = set()

        def add(start: int, end: int, priority: int) -> None:
            value = text[start:end].strip()
            trimmed_start = start + (len(text[start:end]) - len(text[start:end].lstrip()))
            trimmed_end = trimmed_start + len(value)
            if len(re.sub(r"\D", "", value)) < 8:
                return
            if (trimmed_start, trimmed_end) in seen:
                return
            seen.add((trimmed_start, trimmed_end))
            spans.append(
                Span(
                    start=trimmed_start,
                    end=trimmed_end,
                    text=value,
                    entity_type=self.entity_type,
                    detector=self.name,
                    priority=priority,
                )
            )

        for match in self._INTERNATIONAL.finditer(text):
            add(match.start(), match.end(), P_STRUCTURED)

        for label in self._LABEL.finditer(text):
            follow = self._AFTER_LABEL.match(text, label.end())
            if follow:
                add(follow.start(), follow.end(), P_CONTEXTUAL)

        return spans


class DINDetector:
    """Director Identification Numbers.

    A DIN is an 8-digit government identifier bound to a single named
    individual, and it is directly re-identifying: the MCA's public portal
    turns a DIN back into a person. So I treat it as PII.

    I deliberately do *not* redact CIN or SEBI registration numbers. Those
    identify a company or an intermediary, not a person, and they are the
    document's regulatory backbone. This is the precision/recall judgement
    call the brief asks to be made explicitly, and it is recorded in the
    README.
    """

    entity_type = "DIN"
    name = "contextual:din"

    _LABELLED = re.compile(r"(?i)\bDIN\b\s*(?:no\.?|number)?\s*[:.\-]?\s*(\d{6,8})")
    _BARE = re.compile(r"\b\d{8}\b")

    def __init__(self, known_dins: set[str] | None = None) -> None:
        self.known_dins = known_dins or set()

    def find(self, text: str) -> list[Span]:
        spans = []
        for match in self._LABELLED.finditer(text):
            spans.append(
                Span(
                    match.start(1), match.end(1), match.group(1),
                    self.entity_type, self.name, P_STRUCTURED,
                )
            )
        # In the board table the DIN sits alone in its own cell with no
        # label, so a labelled-only rule would miss the densest occurrence.
        # Harvested DINs are matched literally to keep this safe.
        for match in self._BARE.finditer(text):
            if match.group(0) in self.known_dins:
                spans.append(
                    Span(
                        match.start(), match.end(), match.group(0),
                        self.entity_type, f"{self.name}:gazetteer", P_GAZETTEER,
                    )
                )
        return spans


class DateOfBirthDetector:
    """Dates, but only where the surrounding text marks them as a birth date.

    A prospectus is wall-to-wall dates — resolutions, filings, fiscal year
    ends. Only a date introduced by a birth-date cue is PII; redacting the
    rest would corrupt the document and destroy precision.
    """

    entity_type = "DATE_OF_BIRTH"
    name = "contextual:dob"

    _CUE = re.compile(
        r"(?i)\b(?:date\s+of\s+birth|d\.?o\.?b\.?|born\s+on|birth\s+date)\b"
        r"\s*[:\-]?\s*"
    )
    _DATE = re.compile(
        r"(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}\s+[A-Z][a-z]+,?\s+\d{4}"
        r"|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})"
    )

    def find(self, text: str) -> list[Span]:
        spans = []
        for cue in self._CUE.finditer(text):
            match = self._DATE.match(text, cue.end())
            if match:
                spans.append(
                    Span(
                        match.start(), match.end(), match.group(0),
                        self.entity_type, self.name, P_CONTEXTUAL,
                    )
                )
        return spans


class AddressDetector:
    """Postal addresses, anchored on the PIN code.

    Indian addresses have no fixed field order, but they almost always
    terminate in a 6-digit PIN code followed by a state and "India". That
    tail is a reliable anchor, so I find it and then expand *backwards* to
    the nearest structural boundary — a label, a semicolon, a newline, or the
    start of the cell.

    Expanding backwards rather than writing one monolithic regex is what
    makes this work on the board table, where each address is a free-form
    blob like "S. no. 245/104, Sunrise Residency, Orchard Society, lane
    no. 3 Maple Road, ... Example City - 411004 Example State, India".
    """

    entity_type = "ADDRESS"
    name = "contextual:address"

    # The lookbehinds stop an alphanumeric code from being read as a PIN. A
    # chartered engineer's registration number "M-140388" ends in six digits
    # and, without this, anchored an address span across the whole sentence —
    # which then outranked and suppressed the PERSON detection inside it.
    _PIN_TAIL = re.compile(
        r"(?<![A-Za-z])(?<![A-Za-z]-)(?<![\d,.])\b\d{3}\s?\d{3}\b"
        r"(?:\s*[,;]?\s*(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?))?"
        r"(?:\s*[,;]?\s*India)?"
    )
    _LABEL = re.compile(
        r"(?i)(?:registered\s+office|corporate\s+office|address|situated\s+at"
        r"|located\s+at|resides?\s+at|office\s+at)\s*[:\-]?\s*"
    )
    _BOUNDARY = re.compile(r"[;\n\t]|(?<=[a-z])\.\s")
    #: Abbreviations whose full stop is *inside* an address, not the end of a
    #: sentence. Indian addresses are built from them — "S. no. 245/ 104,
    #: Sunrise Residency, ...", "Gat No. 11/3", "H. No. 24" — and treating that dot
    #: as a boundary truncated the span, leaving the house number and building
    #: name unredacted while the rest of the address was replaced.
    _ADDRESS_ABBREV = frozenset({
        "no", "nos", "s", "h", "gat", "sr", "survey", "flat", "plot", "blk",
        "opp", "apt", "bldg", "rd", "st", "ch", "dr", "mr", "mrs", "ms",
    })
    #: Corporate forms that end an organisation name and begin its address.
    _ENTITY_SUFFIX = re.compile(
        r"(?:Private\s+Limited|Limited|Ltd\.?|LLP|LLC|Inc\.?|Corporation|GmbH)"
        r"[,\s]*"
    )
    _MIN_LENGTH = 25
    #: A PIN code plus a place name is already an address line, even when it
    #: is far shorter than a full one — "Example City – 560 001" in an auditor block.
    _SHORT_MIN_LENGTH = 12

    #: Structural words that appear in Indian street addresses. Used for the
    #: no-PIN case, where density of these markers is the only signal.
    _MARKERS = (
        "tower", "floor", "level", "wing", "block", "plot", "survey", "s. no",
        "road", "marg", "street", "lane", "cross", "circle", "chowk",
        "nagar", "society", "colony", "apartment", "apartments", "flat",
        "bungalow", "villa", "house", "bhavan", "chambers", "campus",
        "centre", "center", "complex", "estate", "premises", "farms",
        "village", "taluka", "tehsil", "district", "sector", "phase",
        "gat no", "plot no", "survey no", "s. no", "h. no", "flat no",
        "gat  no", "khasra", "wadi", "peth", "pada",
        "industrial area", "business park", "techno", "annexe", "opp",
        "opposite", "behind", "near", "off ",
    )
    _CITY_HINT = re.compile(
        r"(?i)\b(?:pune|mumbai|bombay|delhi|bengaluru|bangalore|chennai|"
        r"kolkata|hyderabad|ahmedabad|nagpur|thane|noida|gurugram|bhopal|"
        r"chakan|baner|maharashtra|gujarat|karnataka|india)\b"
    )

    #: Splits a block into candidate address segments. A label ("… as set
    #: forth below:") and a sentence end both terminate a segment; without
    #: this the whole line was treated as one address and swallowed the
    #: person named at the start of it.
    _SEGMENT_BREAK = re.compile(r"[\n\t;:]|(?<=[a-z])\.\s+(?=[A-Z])")

    @classmethod
    def _is_abbreviation(cls, window: str, match: re.Match) -> bool:
        """True if this full stop closes an address abbreviation, not a clause."""
        if match.group(0)[0] in ";:\n\t":
            return False
        preceding = re.search(r"([A-Za-z]+)\.\s*$", window[: match.end()])
        return bool(preceding and preceding.group(1).lower() in cls._ADDRESS_ABBREV)

    @classmethod
    def _segments(cls, text: str):
        """Yield ``(offset, segment)`` pairs for a block."""
        start = 0
        for match in cls._SEGMENT_BREAK.finditer(text):
            if cls._is_abbreviation(text, match):
                continue
            yield start, text[start : match.start()]
            start = match.end()
        yield start, text[start:]

    #: A unit or premises designator: "C-101", "O-3", "801-804", "No 3".
    _UNIT_CODE = re.compile(r"\b[A-Z]?-?\d{1,4}(?:\s?-\s?\d{1,4})?\b")
    #: Grammatical function words. Their presence marks a clause, not an
    #: address — addresses are noun phrases.
    _FUNCTION_WORDS = re.compile(
        r"(?i)\b(?:to|of|as|for|which|their|under|with|that|is|are|was|were"
        r"|has|have|been|be|by|from|shall|may|such|this|these|those|include"
        r"|including|pursuant|required|issued|dated|and\s+the)\b"
    )

    @classmethod
    def _is_address_after_entity(cls, line: str) -> bool:
        """True for "<Company Name> <address>" run together on one line.

        The intermediary listings do this constantly — "MUFG Intime India
        Private Limited (Formerly Harbor Registry Private Limited) C-101,
        Embassy 247". The address tail carries no PIN code and no structural
        keyword, so neither the anchored nor the marker path sees it, and the
        company name gets replaced while its address survives.

        This is the mirror of the suffix trim applied to the anchored path:
        whatever follows the last corporate form is the address, provided it
        actually looks like one — a comma and a unit designator, which is the
        minimum an address line of this shape ever has.
        """
        suffix = None
        for suffix in cls._ENTITY_SUFFIX.finditer(line):
            pass
        if suffix is None:
            return False
        tail = line[suffix.end() :].strip(" ()")
        if not 12 <= len(tail) <= 60 or "," not in tail:
            return False
        # An address tail is a short run of comma-separated fragments. Prose
        # is not: "…LLP, independent practicing company secretary, to include
        # their name as required under Section 26…" also follows a corporate
        # form and also contains commas and numbers, so the discriminator has
        # to be grammatical. Function words mean this is a clause, not an
        # address.
        if cls._FUNCTION_WORDS.search(tail):
            return False
        return bool(cls._UNIT_CODE.search(tail)) and bool(re.search(r"[A-Z][a-z]", tail))

    @classmethod
    def _marker_hits(cls, value: str) -> set[str]:
        """Address markers present as whole words.

        Substring matching read "Compliance Officer" as containing the marker
        "office", which is exactly the kind of accidental hit that turns a
        sentence into an address.
        """
        lowered = value.lower()
        return {
            marker
            for marker in cls._MARKERS
            if re.search(r"\b" + re.escape(marker.strip()) + r"\b", lowered)
        }

    def find(self, text: str) -> list[Span]:
        spans = []
        for tail in self._PIN_TAIL.finditer(text):
            end = tail.end()
            window_start = max(0, tail.start() - 220)
            window = text[window_start : tail.start()]

            label = None
            for label in self._LABEL.finditer(window):
                pass  # take the last label before the PIN
            if label is not None:
                start = window_start + label.end()
            else:
                boundary = None
                for candidate_boundary in self._BOUNDARY.finditer(window):
                    if self._is_abbreviation(window, candidate_boundary):
                        continue
                    boundary = candidate_boundary  # keep the last real one
                start = window_start + (boundary.end() if boundary else 0)

            # An address does not include the company that sits at it. The
            # document writes "Apex Securities Limited Apex Venture House
            # ... Mumbai - 400 025" as one run of text; without this, the
            # address span swallows the organisation name, the two detectors
            # collide, and the longer address span wins — losing the ORG
            # entirely. Start the address after the last corporate suffix.
            suffix = None
            for suffix in self._ENTITY_SUFFIX.finditer(text, start, tail.start()):
                pass
            if suffix is not None:
                start = suffix.end()

            while start < tail.start() and text[start] in " ,:-–—\t":
                start += 1

            candidate = text[start:end].strip()
            minimum = (
                self._SHORT_MIN_LENGTH
                if self._CITY_HINT.search(candidate)
                else self._MIN_LENGTH
            )
            if len(candidate) < minimum:
                continue
            if not re.search(r"[A-Za-z]{3}", candidate):
                continue
            # An address must name a place or contain a structural address
            # word. Requiring this — rather than accepting any comma-bearing
            # run of text before a six-digit number — is what keeps ordinary
            # prose that happens to end in a numeric code out of the results.
            has_place = bool(self._CITY_HINT.search(candidate))
            has_marker = bool(
                re.search(
                    r"(?i)\b(road|street|marg|nagar|society|apartment|floor|tower"
                    r"|village|taluka|district|complex|park|lane|plot|block"
                    r"|wing|building|house|campus|centre|center|estate|colony"
                    r"|premises|chambers|sector|phase|flat|survey|opposite|behind)\b",
                    candidate,
                )
            )
            if not has_place and not has_marker:
                continue
            spans.append(
                Span(
                    start, start + len(candidate), candidate,
                    self.entity_type, self.name, P_CONTEXTUAL,
                )
            )

        spans.extend(self._find_without_pin(text, spans))
        return spans

    def _find_without_pin(self, text: str, existing: list[Span]) -> list[Span]:
        """Address lines that carry no PIN code.

        Registered-office lines are routinely split across table cells, so the
        PIN ends up in a different block from the street — "201, Tower-2,
        Horizon Business Centre Off Lakeside Avenue, West End" has no PIN anywhere
        in it. The fallback is marker density: two or more distinct structural
        address words plus comma separation. Requiring *two* is what keeps a
        lone "Unit 2 in Chakan" or "Total Chakan Unit No. 3" out.
        """
        spans: list[Span] = []
        for segment_offset, raw_segment in self._segments(text):
            line = raw_segment.strip()
            if len(line) < 20 or "," not in line:
                continue
            offset = segment_offset + (len(raw_segment) - len(raw_segment.lstrip()))
            if any(
                span.start < offset + len(line) and offset < span.end
                for span in existing
            ):
                continue
            markers = self._marker_hits(line)
            if len(markers) < 2 and not self._is_address_after_entity(line):
                continue

            # Same rule as the PIN-anchored path: the organisation named at
            # the head of the line is not part of its address.
            suffix = None
            for suffix in self._ENTITY_SUFFIX.finditer(line):
                pass
            if suffix is not None:
                offset += suffix.end()
                line = line[suffix.end() :]
                if len(line) < 20:
                    continue

            spans.append(
                Span(
                    offset, offset + len(line), line,
                    self.entity_type, f"{self.name}:markers",
                    # Outranks the gazetteers (60) but yields to the
                    # deterministic detectors (80+). A line that is
                    # structurally an address *is* an address, and must not be
                    # fragmented by a gazetteer hit inside it: "S. no. 245/
                    # 104, Sunrise Residency, Orchard Society" was having
                    # only "Orchard Society" replaced — because spaCy reads
                    # that locality as a person — leaving the house number and
                    # building name in the clear.
                    P_GAZETTEER + 1,
                )
            )
        return spans


# --------------------------------------------------------------------------
# Open-class detectors
# --------------------------------------------------------------------------


class GazetteerDetector:
    """Literal, case-insensitive matching of harvested entity strings.

    This is the recall engine. Once "Dev Mehra" has been confidently
    identified once — from a "Contact Person:" label or a clean sentence —
    every other occurrence is caught deterministically, including in table
    cells where the NER model has no context to work with.
    """

    name = "gazetteer"

    #: Separators allowed *between* the tokens of a gazetteer term.
    _SEPARATOR = r"[\s,.\-–—&/]+"

    def __init__(self, entity_type: str, terms: Iterable[str]) -> None:
        self.entity_type = entity_type
        self.terms = sorted({t.strip() for t in terms if t and t.strip()}, key=len, reverse=True)
        self.pattern = (
            re.compile(
                r"(?<![\w@.])(?:"
                + "|".join(self._to_pattern(t) for t in self.terms)
                + r")(?![\w@])",
                re.IGNORECASE,
            )
            if self.terms
            else None
        )

    @classmethod
    def _to_pattern(cls, term: str) -> str:
        """Compile a term so punctuation variants still match.

        The document writes the same auditor as "Alder & Finch LLP" in one
        place and "Alder & Finch, LLP" in another. Literal matching learns
        the entity from the first and then misses the second over a single
        comma — a silent recall hole that a spot-check of the output would
        never reveal. Matching on the token sequence, with punctuation treated
        as flexible separator, closes it.
        """
        tokens = [t for t in re.split(r"[^\w]+", term) if t]
        if not tokens:
            return re.escape(term)
        return cls._SEPARATOR.join(re.escape(token) for token in tokens)

    def find(self, text: str) -> list[Span]:
        if self.pattern is None:
            return []
        return [
            Span(
                m.start(), m.end(), m.group(0),
                self.entity_type, f"{self.name}:{self.entity_type.lower()}",
                P_GAZETTEER,
            )
            for m in self.pattern.finditer(text)
        ]


class CorporateEntityDetector:
    """Named legal entities found by their corporate suffix, without NER.

    This exists because spaCy's small model is unreliable on exactly the
    entities that matter most here. On the real text it returns nothing at
    all for "(Formerly Harbor Registry Private Limited)", and for the line
    beginning "Apex Securities Limited Apex Venture House ..." it finds
    only ``Mumbai`` and ``India``. Those are registrar and book-running
    lead manager names — squarely in scope — and a model-only pipeline drops
    them silently.

    An Indian company name ends in a fixed, small set of corporate forms, and
    the tokens before it are capitalised. That is a reliable enough grammar to
    match deterministically, so this detector recovers the whole class
    independently of whether the model happened to fire.
    """

    entity_type = "ORG"
    name = "regex:corporate"

    _SUFFIX = (
        r"(?:Private\s+Limited|Public\s+Limited|Limited|Ltd\.?|LLP|L\.L\.P\.?"
        r"|LLC|L\.L\.C\.?|Inc\.?|Incorporated|Corporation|Corp\.?|GmbH|PLC"
        r"|N\.?V\.?|B\.?V\.?|A\.?G\.?|S\.?A\.?|Pte\.?\s+Ltd\.?"
        r"|Family\s+Trust|HUF)"
    )
    #: One to six capitalised tokens, then a corporate form. "&" and "." are
    #: allowed inside the name ("Harbor & Co. LLP").
    pattern = re.compile(
        r"\b((?:[A-Z][\w'’.\-]*\s+|&\s+|[A-Z]{2,}\s+){1,6}" + _SUFFIX + r")\b"
    )

    #: Capitalised words that introduce a company name without being part of
    #: it — "(Formerly Harbor Registry Private Limited)". Left in place they
    #: produce a superset span, which still redacts correctly but drifts the
    #: boundary and costs strict-match precision.
    _LEADING_NOISE = re.compile(
        r"^(?:Formerly|Erstwhile|Namely|Viz\.?|Including|Between|Amongst|Among"
        r"|And|Or|From|With|By|To)\s+"
    )

    def find(self, text: str) -> list[Span]:
        spans = []
        for match in self.pattern.finditer(text):
            value = match.group(1).strip()
            start = match.start(1)

            trimmed = self._LEADING_NOISE.sub("", value)
            while trimmed != value:
                start += len(value) - len(trimmed)
                value = trimmed
                trimmed = self._LEADING_NOISE.sub("", value)

            if is_allowlisted_org(value) or is_defined_term(value):
                continue
            if is_only_generic(value):
                continue
            spans.append(
                Span(
                    start, start + len(value), value,
                    self.entity_type, self.name, P_CONTEXTUAL,
                )
            )
        return spans


class SpacyEntityDetector:
    """spaCy NER for PERSON and ORG, filtered through the allowlist."""

    name = "spacy"

    def __init__(self, nlp, entity_type: str, spacy_labels: tuple[str, ...]) -> None:
        self.nlp = nlp
        self.entity_type = entity_type
        self.spacy_labels = spacy_labels

    def find(self, text: str) -> list[Span]:
        doc = self.nlp(text)
        return self.spans_from_ents(
            [(e.start_char, e.text, e.label_) for e in doc.ents]
        )

    def spans_from_ents(self, ents: list[tuple[int, str, str]]) -> list[Span]:
        """Build spans from raw ``(start_char, text, label)`` tuples.

        Taking tuples rather than a spaCy ``Doc`` lets the pipeline run NER
        exactly once and reuse the results across both passes — the model is
        by far the most expensive stage, and the harvest pass would otherwise
        double the runtime for no new information.
        """
        spans = []
        for start_char, raw, label in ents:
            if label not in self.spacy_labels:
                continue
            value = raw.strip()
            if not self.keep(value):
                continue
            offset = start_char + (len(raw) - len(raw.lstrip()))
            spans.append(
                Span(
                    offset, offset + len(value), value,
                    self.entity_type, f"{self.name}:{self.entity_type.lower()}",
                    P_MODEL,
                )
            )
        return spans

    def keep(self, value: str) -> bool:
        if self.entity_type == "PERSON":
            return not is_person_noise(value)
        if self.entity_type == "ORG":
            return not is_allowlisted_org(value) and len(value) > 3
        return True


def build_detectors(
    nlp=None,
    person_terms: Iterable[str] = (),
    org_terms: Iterable[str] = (),
    known_dins: Iterable[str] = (),
) -> list[Detector]:
    """Assemble the active detector set.

    Order is irrelevant — conflicts are settled by ``resolve_overlaps`` using
    the priority bands, not by registration order.
    """
    detectors: list[Detector] = [
        EmailDetector(),
        CorporateEntityDetector(),
        WebsiteDetector(),
        SSNDetector(),
        CreditCardDetector(),
        IPAddressDetector(),
        PhoneDetector(),
        DINDetector(set(known_dins)),
        DateOfBirthDetector(),
        AddressDetector(),
    ]
    if person_terms:
        detectors.append(GazetteerDetector("PERSON", person_terms))
    if org_terms:
        detectors.append(GazetteerDetector("ORG", org_terms))
    if nlp is not None:
        detectors.append(SpacyEntityDetector(nlp, "PERSON", ("PERSON",)))
        detectors.append(SpacyEntityDetector(nlp, "ORG", ("ORG",)))
    return detectors
