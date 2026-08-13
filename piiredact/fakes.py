"""Consistent pseudonymisation: real value in, stable fake value out.

Two properties matter here, and they pull against each other:

*Unlinkability* — the fake must not leak the original.
*Coherence* — the document has to still make sense. A prospectus that names
its Managing Director in forty places needs the same fake name in all forty,
or the disclosures become nonsense and the redaction is obvious.

I chose coherence via a **seeded, memoised mapping**: the first time a value
is seen it gets a fake from Faker; every later occurrence reuses it. The seed
makes runs reproducible, which is what lets me diff two runs and lets my
evaluation numbers be re-derived rather than taken on trust.

The tradeoff I accept: consistent mapping preserves the *frequency and
co-occurrence structure* of the original entities. For a public prospectus
that is the right call. For a genuinely adversarial release you would want
per-occurrence randomisation and would give up readability for it.

To extend: register a generator for the new entity type in ``_GENERATORS``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from faker import Faker


def _match_case(original: str, replacement: str) -> str:
    """Carry the original's casing over to the fake.

    The promoter tables shout their names in caps —
    ``OUR PROMOTERS: ARJUN MEHTA, ...`` — while body prose uses
    title case. Ignoring that makes the redaction stick out.
    """
    letters = [c for c in original if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return replacement.upper()
    if letters and all(c.islower() for c in letters):
        return replacement.lower()
    return replacement


class FakeFactory:
    """Assigns and remembers a fake value for every real value it sees."""

    def __init__(self, seed: int = 20251210, locale: str = "en_IN") -> None:
        # en_IN keeps the substitutions plausible for an Indian filing: a
        # Pune address replaced by a Kansas one would be its own kind of
        # information leak, and would look wrong to any reader.
        self._faker = Faker(locale)
        Faker.seed(seed)
        self._faker.seed_instance(seed)
        self._memo: dict[tuple[str, str], str] = {}
        # The canonical value is the lookup key, but the audit file should
        # retain the first human-readable source spelling that was observed.
        self._originals: dict[tuple[str, str], str] = {}
        self._used: set[str] = set()

    # -- public API ------------------------------------------------------

    def fake_for(self, entity_type: str, original: str) -> str:
        """Return the stable fake for ``original``, minting one if needed."""
        key = (entity_type, self._canonical(entity_type, original))
        if key not in self._memo:
            # A random-looking replacement is not safe if it happens to equal
            # the source value, especially for short digit-only identifiers.
            # Compare canonical forms so punctuation variants cannot slip
            # through as a false redaction.
            for _ in range(200):
                candidate = self._mint(entity_type, original)
                if self._canonical(entity_type, candidate) != key[1]:
                    self._memo[key] = candidate
                    break
            else:
                raise RuntimeError(f"could not mint a distinct fake for {entity_type}")
            self._originals[key] = original
        return _match_case(original, self._memo[key])

    @property
    def mapping(self) -> dict[tuple[str, str], str]:
        return dict(self._memo)

    def mapping_rows(self) -> list[dict[str, str]]:
        """Safe audit rows for the output directory.

        A cleartext real-to-fake mapping would defeat the purpose of a
        redacted release. I therefore keep the source value only in memory
        while processing, then emit its SHA-256 digest for reproducibility and
        audit correlation without making the output directory re-identifying.
        """
        rows = []
        for key, replacement in sorted(self._memo.items()):
            entity_type, _canonical = key
            rows.append(
                {
                    "entity_type": entity_type,
                    "source_sha256": hashlib.sha256(
                        self._originals[key].encode("utf-8")
                    ).hexdigest(),
                    "replacement": replacement,
                }
            )
        return rows

    # -- internals -------------------------------------------------------

    @staticmethod
    def _canonical(entity_type: str, value: str) -> str:
        """Normalise semantically equivalent renderings to one fake.

        Word-run boundaries and punctuation vary throughout the document:
        ``+ 91 (20) 6729 5100`` and ``+91 20 6729 5100`` are the same phone
        number, and ``Alder & Finch LLP`` also appears as
        ``Alder & Finch, LLP``. Each pair must receive one fake value.

        Emails and websites deliberately retain punctuation because it is
        part of the identifier rather than merely presentation.
        """
        if entity_type == "PHONE":
            digits = re.sub(r"\D", "", value)
            # Country-code presentation varies; the last ten digits identify
            # the Indian national number used throughout this filing.
            return digits[-10:] if len(digits) >= 10 else digits
        if entity_type in {"PERSON", "ORG"}:
            return " ".join(re.findall(r"[a-z0-9]+", value.lower()))
        return re.sub(r"[\s \-–—]+", " ", value).strip().lower()

    def _unique(self, generator) -> str:
        """Draw from ``generator`` until we get a value we have not used."""
        for _ in range(200):
            candidate = generator()
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
        # Collision-proof fallback; effectively unreachable at this scale.
        candidate = f"{generator()}-{len(self._used)}"
        self._used.add(candidate)
        return candidate

    def _mint(self, entity_type: str, original: str) -> str:
        generator = _GENERATORS.get(entity_type)
        if generator is None:
            return f"[{entity_type}]"
        return self._unique(lambda: generator(self._faker, original))


# -- per-type generators ---------------------------------------------------
# Each takes (faker, original) so a generator can mirror the shape of what it
# replaces — matching digit-grouping on a phone number, keeping a "Limited"
# suffix on a company — without any of the original's content surviving.


def _person(faker: Faker, original: str) -> str:
    parts = original.split()
    if len(parts) >= 3:
        return f"{faker.first_name()} {faker.first_name()} {faker.last_name()}"
    return faker.name()


def _email(faker: Faker, original: str) -> str:
    local, _, _domain = original.partition("@")
    # Preserve the local-part's shape (dotted vs flat) so downstream format
    # checks behave the same, without carrying over the real name.
    if "." in local:
        return f"{faker.first_name().lower()}.{faker.last_name().lower()}@example.com"
    return f"{faker.user_name().lower()}@example.com"


def _phone(faker: Faker, original: str) -> str:
    digits = re.sub(r"\D", "", original)
    national = digits[-10:] if len(digits) >= 10 else digits
    body = "".join(str(faker.random_digit()) for _ in range(len(national)))
    if original.strip().startswith("+"):
        return f"+91 {body[:5]} {body[5:]}" if len(body) == 10 else f"+91 {body}"
    return body


def _organisation(faker: Faker, original: str) -> str:
    suffix_match = re.search(
        r"(?i)(\s+(?:private\s+limited|public\s+limited|limited|ltd\.?|"
        r"llp|l\.l\.p\.?|llc|l\.l\.c\.?|inc\.?|incorporated|corporation|"
        r"corp\.?|gmbh|plc|n\.?v\.?|b\.?v\.?|a\.?g\.?|s\.?a\.?|"
        r"pte\.?\s+ltd\.?|family\s+trust|trust|huf))$",
        original,
    )
    suffix = suffix_match.group(1) if suffix_match else ""
    # Faker's company provider may add its own legal form. Remove it before
    # restoring the exact legal form from the source value.
    base = re.sub(
        r"(?i)[,\s]+(?:ltd\.?|pvt\.?\s*ltd\.?|private\s+limited|"
        r"limited|llp|inc\.?|corporation|corp\.?)$",
        "",
        faker.company(),
    ).strip(" ,")
    return f"{base}{suffix}" if suffix else base


def _address(faker: Faker, _original: str) -> str:
    return faker.address().replace("\n", ", ")


def _din(faker: Faker, original: str) -> str:
    width = len(re.sub(r"\D", "", original)) or 8
    return "".join(str(faker.random_digit()) for _ in range(width))


def _ssn(faker: Faker, _original: str) -> str:
    first = faker.random_int(1, 899)
    while first == 666:
        first = faker.random_int(1, 899)
    return f"{first:03d}-{faker.random_int(1, 99):02d}-{faker.random_int(1, 9999):04d}"


def _credit_card(faker: Faker, original: str) -> str:
    separator = "-" if "-" in original else (" " if " " in original else "")
    number = faker.credit_card_number()
    if separator:
        groups = [number[i : i + 4] for i in range(0, len(number), 4)]
        return separator.join(groups)
    return number


def _ip_address(faker: Faker, original: str) -> str:
    return faker.ipv6() if ":" in original else faker.ipv4()


def _date_of_birth(faker: Faker, _original: str) -> str:
    return faker.date_of_birth(minimum_age=25, maximum_age=80).strftime("%B %d, %Y")


def _website(faker: Faker, original: str) -> str:
    replacement = f"www.{faker.domain_word()}.example.com"
    lowered = original.lower()
    if lowered.startswith("https://"):
        return f"https://{replacement}"
    if lowered.startswith("http://"):
        return f"http://{replacement}"
    return replacement


_GENERATORS = {
    "PERSON": _person,
    "EMAIL": _email,
    "PHONE": _phone,
    "ORG": _organisation,
    "ADDRESS": _address,
    "DIN": _din,
    "SSN": _ssn,
    "CREDIT_CARD": _credit_card,
    "IP_ADDRESS": _ip_address,
    "DATE_OF_BIRTH": _date_of_birth,
    "WEBSITE": _website,
}


@dataclass
class RedactionLedger:
    """Everything the run produced, for the README and evaluation report."""

    replacements: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    blocks_touched: int = 0

    def record(self, entity_type: str) -> None:
        self.replacements += 1
        self.by_type[entity_type] = self.by_type.get(entity_type, 0) + 1
