"""Things that look like PII but are not, and must survive redaction.

This file is where my precision comes from, and it encodes a deliberate
scoping decision that I want to be explicit about (the brief asks for
exactly that).

A red herring prospectus is a *regulatory* document. It is saturated with
organisation names — but most of them identify regulators, statutes, stock
exchanges, depositories and rating agencies, not people or private parties.
Redacting "SEBI", "the Companies Act, 2013", "BSE" and "Reserve Bank of
India" would:

  * destroy the document's meaning, since the disclosures are unreadable
    without the statutory framework they cite, and
  * tank precision, because none of it is personally identifying.

So: **I redact the issuer, its group/promoter-linked entities, and private
counterparties. I keep regulators, statutes, exchanges and market
infrastructure.** Everything kept is a matter of public record and identifies
an institution rather than a person.

To extend: add a term here (matching is case-insensitive on whole words) and
it becomes immune to the organisation detector.
"""

from __future__ import annotations

import re

#: Regulators, statutes, exchanges, depositories and market infrastructure.
INSTITUTIONAL_ALLOWLIST: set[str] = {
    # Regulators and government bodies
    "sebi", "securities and exchange board of india", "rbi",
    "reserve bank of india", "roc", "registrar of companies",
    "ministry of corporate affairs", "mca", "government of india",
    "ministry of commerce and industry", "department of commerce",
    "directorate general of foreign trade", "dgft", "income tax department",
    "central board of direct taxes", "cbdt", "gst council", "irdai",
    "competition commission of india", "nclt", "nclat", "supreme court",
    "high court", "state government", "maharashtra state government",
    "central processing centre", "regional director",
    # Exchanges, depositories, registrars of the market itself
    "bse", "nse", "bse limited", "national stock exchange",
    "national stock exchange of india limited", "stock exchanges",
    "nsdl", "cdsl", "national securities depository limited",
    "central depository services", "clearing corporation",
    "nse clearing limited", "indian clearing corporation limited",
    # Statutes, regulations and frameworks
    "companies act", "companies act, 2013", "companies act, 1956",
    "sebi icdr regulations", "icdr regulations", "sebi listing regulations",
    "sebi lodr regulations", "securities contracts", "scra", "sccr",
    "fema", "foreign exchange management act", "income tax act",
    "ind as", "indian accounting standards", "gaap", "ifrs",
    "insolvency and bankruptcy code", "prevention of money laundering act",
    "sebi merchant bankers regulations", "sebi mutual funds regulations",
    "sebi fpi regulations", "sebi aif regulations", "sebi vcf regulations",
    "sebi sbeb regulations", "sebi insider trading regulations",
    "sebi takeover regulations", "maharashtra industrial policy",
    # Standards, schemes and indices referenced generically
    "meis", "rodtep", "gst", "upi", "asba", "npci",
    "national payments corporation of india", "fbil", "crisil", "icra",
    "care ratings", "india ratings",
    # Generic corporate self-reference used throughout the document
    "our company", "the company", "our board", "the board",
    "our promoters", "the promoters", "our group companies",
    "board of directors", "audit committee", "nomination and remuneration committee",
    "stakeholders relationship committee", "risk management committee",
    "corporate social responsibility committee", "csr committee",
    "book running lead managers", "brlms", "syndicate members",
    "anchor investors", "qualified institutional buyers", "qibs",
    "non-institutional investors", "retail individual investors",
    "eligible employees", "selling shareholders", "underwriters",
}

#: Titles/roles that spaCy sometimes swallows into a PERSON span.
PERSON_STOPWORDS: set[str] = {
    "chairman", "director", "managing director", "joint managing director",
    "executive director", "independent director", "whole-time director",
    "whole time director", "company secretary", "compliance officer",
    "chief financial officer", "chief executive officer", "promoter",
    "promoters", "shareholder", "shareholders", "auditor", "auditors",
    "statutory auditor", "peer review", "contact person", "investor",
    "mr", "mrs", "ms", "dr", "shri", "smt", "sir", "madam",
    "limited", "private limited", "llp", "trust", "fiscal", "fiscals",
    "equity shares", "equity share", "offer", "bid", "allotment",
    "rupees", "lakh", "crore", "million", "billion",
}

#: Words that mark a capitalised phrase as an institution rather than a
#: private company, even if it is not in the allowlist verbatim.
INSTITUTIONAL_MARKERS: tuple[str, ...] = (
    "act", "regulations", "rules", "guidelines", "policy", "scheme",
    "circular", "notification", "tribunal", "court", "ministry",
    "department", "commission", "authority", "board of india",
    "stock exchange", "depository", "government",
)

#: Domain vocabulary that spaCy repeatedly mislabels as PERSON or ORG.
#: A capitalisation test cannot catch these — "Bid Amount", "Floor Price" and
#: "Key Managerial Personnel" are all title case. Any candidate containing one
#: of these tokens is document terminology, not a person or a private company.
DOMAIN_NOISE: set[str] = {
    # Offer mechanics
    "bid", "bids", "bidder", "bidders", "bidding", "offer", "offers",
    "price", "amount", "allotment", "allottee", "allottees", "allotted",
    "issue", "issuer", "fresh", "anchor", "escrow", "cut", "cap", "floor",
    "syndicate", "underwriter", "underwriters", "prospectus", "abridged",
    "subscription", "oversubscription", "refund", "revision", "withdrawal",
    "application", "applications", "form", "forms", "slip",
    "acknowledgement", "mandate", "cutoff", "basis", "designated",
    # Securities and capital
    "share", "shares", "equity", "preference", "capital", "shareholder",
    "shareholders", "shareholding", "promoter", "promoters", "stake",
    "securities", "instrument", "instruments", "dematerialised", "demat",
    "lock", "lien", "pledge", "dividend", "bonus", "split", "esop", "esos",
    # Accounts, banking, market plumbing
    "account", "accounts", "bank", "banker", "bankers", "banking", "branch",
    "broker", "brokers", "depository", "participant", "registrar",
    "agent", "agents", "transfer", "clearing", "settlement", "custodian",
    "deposit", "deposits",
    "nro", "nre", "asba", "upi", "qib", "qibs", "nii", "niis", "rii", "riis",
    "fpi", "fii", "aif", "vcf", "mutual", "fund", "funds", "investor",
    "investors", "institutional", "individual", "retail", "eligible",
    # Governance and reporting
    "key", "managerial", "personnel", "committee", "meeting", "resolution",
    "auditor", "auditors", "audit", "report", "statement", "statements",
    "financial", "fiscal", "quarter", "annexure", "schedule", "corrigenda",
    "corrigendum", "addendum", "memorandum", "articles", "association",
    "defaulter", "wilful", "material", "restated", "consolidated",
    # Measures, ratios and units
    "cagr", "margin", "ebitda", "pat", "roce", "roe", "revenue", "turnover",
    "growth", "volume", "capacity", "utilisation", "gigawatt", "megawatt",
    "kilowatt", "watt", "volt", "volts", "amperes", "hour", "hours",
    "kilometers", "kilometres", "metric", "tonne", "tonnes", "percentage",
    # Places, buildings and infrastructure words that appear inside addresses
    "floor", "tower", "chambers", "complex", "apartment", "apartments",
    "building", "premises", "facility", "facilities", "plant", "unit",
    "road", "street", "marg", "lane", "nagar", "society", "colony", "plot",
    "village", "taluka", "district", "showroom", "hospital", "park",
    "industrial", "estate", "campus", "centre", "center", "office",
    # Media, technology and misc. document furniture
    "website", "newspaper", "daily", "marathi", "english", "hindi",
    "circulated", "widely", "edition", "advertisement", "notice",
    "air", "conditioning", "photo", "voltaic", "solar", "battery", "energy",
    "storage", "system", "systems", "circuit", "winding", "magnet", "wire",
    "wires", "cable", "cables", "operational", "secondary", "primary",
    "registered", "certified", "iso", "standard", "specification",
    "thereto", "thereof", "herein", "pursuant",
    "reference", "rate", "rates", "listing", "bhavan", "index", "benchmark",
    # Hindi vocabulary from government scheme names — "Deen Dayal Upadhyaya
    # Gram Jyoti Yojana", "PM Kisan Urja Suraksha" — which read as two-token
    # personal names to an English NER model.
    "gram", "jyoti", "yojana", "kisan", "urja", "suraksha", "abhiyan",
    "bharat", "swachh", "vikas", "kendra", "sangathna", "kamgar", "udyog",
}

#: Corporate-form tokens that are decisive wherever they appear. "Limited",
#: "LLP" and "GmbH" have no ordinary-language sense in this document.
STRONG_ENTITY_MARKERS: frozenset[str] = frozenset({
    "limited", "ltd", "llp", "inc", "incorporated", "corporation", "corp",
    "gmbh", "plc", "ab", "nv", "spa", "huf", "trust",
})

#: Tokens that mark a legal entity only in trailing position. "Associates"
#: ends a firm name but also appears mid-phrase in prose; "Industries" and
#: "Solutions" behave the same way. Requiring them near the end is what stops
#: "export promotion capital goods" and "international monetary fund" from
#: being read as private companies.
WEAK_ENTITY_MARKERS: frozenset[str] = frozenset({
    "co", "company", "associates", "consultants", "partners", "partnership",
    "firm", "ventures", "holdings", "industries", "enterprises",
    "technologies", "solutions", "securities", "systems", "works", "mills",
    "sons", "brothers", "group",
})

#: Generic on their own — a candidate made only of these names no entity.
GENERIC_ENTITY_TOKENS: frozenset[str] = frozenset(
    STRONG_ENTITY_MARKERS
    | WEAK_ENTITY_MARKERS
    | {"the", "of", "and", "private", "public", "family", "our", "its"}
)

LEGAL_ENTITY_MARKERS: frozenset[str] = STRONG_ENTITY_MARKERS | WEAK_ENTITY_MARKERS

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")

#: Terms the document defines about itself. Populated at runtime from the
#: prospectus's own glossary tables — see ``pipeline.harvest_glossary``.
#: This is the single highest-leverage precision control in the tool: a
#: phrase the document formally defines is, by construction, terminology.
_GLOSSARY: set[str] = set()


def load_glossary(terms) -> None:
    """Install the document's defined terms as a dynamic allowlist."""
    _GLOSSARY.clear()
    for term in terms:
        # Glossary headwords are often slash-separated alternatives:
        # "Board/ Board of Directors", "Chief Executive Officer/ CEO".
        for variant in re.split(r"[/;]", term):
            normalised = _normalise(variant)
            if len(normalised) > 2:
                _GLOSSARY.add(normalised)


def is_defined_term(value: str) -> bool:
    """True if the document's own glossary defines this phrase."""
    normalised = _normalise(value)
    if not normalised:
        return False
    if normalised in _GLOSSARY:
        return True
    # "the Bid Amount" / "Bid Amounts" against a headword of "Bid Amount".
    stripped = re.sub(r"^(?:the|our|its)\s+", "", normalised)
    return stripped in _GLOSSARY or stripped.rstrip("s") in _GLOSSARY


def has_legal_entity_marker(value: str) -> bool:
    """True if the phrase carries a corporate-form token in a valid position.

    Strong markers count anywhere; weak markers only in the last two tokens,
    where a company name actually puts them.
    """
    tokens = _normalise(value).split()
    if not tokens:
        return False
    if set(tokens) & STRONG_ENTITY_MARKERS:
        return True
    return bool(set(tokens[-2:]) & WEAK_ENTITY_MARKERS)


def is_only_generic(value: str) -> bool:
    """True if the phrase is nothing but corporate boilerplate.

    Catches the fragments spaCy carves out of longer names — "Private
    Limited", "Family Trust", "Company" — which carry no identity at all.
    """
    tokens = _normalise(value).split()
    return bool(tokens) and all(token in GENERIC_ENTITY_TOKENS for token in tokens)


def contains_domain_noise(value: str) -> bool:
    tokens = set(_normalise(value).split())
    return bool(tokens & DOMAIN_NOISE)


def _normalise(value: str) -> str:
    return " ".join(_WORD_SPLIT.split(value.lower())).strip()


def is_allowlisted_org(value: str) -> bool:
    """True if ``value`` is an institution we deliberately keep in the clear."""
    normalised = _normalise(value)
    if not normalised:
        return True
    if normalised in INSTITUTIONAL_ALLOWLIST:
        return True
    # Strip a leading article — "the Companies Act" vs "Companies Act".
    if normalised.startswith("the ") and normalised[4:] in INSTITUTIONAL_ALLOWLIST:
        return True
    # A phrase containing an allowlisted regulator is itself regulatory,
    # e.g. "SEBI ICDR Regulations, 2018".
    for term in INSTITUTIONAL_ALLOWLIST:
        if len(term) > 6 and term in normalised:
            return True
    return any(marker in normalised for marker in INSTITUTIONAL_MARKERS)


def is_redactable_org(value: str, family_names: set[str] | None = None) -> bool:
    """Decide whether an organisation candidate is PII we should replace.

    The rule is deliberately strict, because "organisation" is the noisiest
    class in this document by an order of magnitude. A candidate qualifies
    only if it is a *named legal entity*:

      * it carries a corporate-form token ("... Private Limited", "... AB",
        "... Family Trust"), **or**
      * it shares a surname with one of the promoters, which is how the
        family's unsuffixed group entities show up.

    Everything else — defined terms, regulators, generic noun phrases — is
    left alone. This costs some recall on entities named without a corporate
    suffix, and that FN class is called out explicitly in the README.
    """
    normalised = _normalise(value)
    if len(normalised) < 4 or is_only_generic(value):
        return False
    if is_allowlisted_org(value) or is_defined_term(value):
        return False
    if has_legal_entity_marker(value):
        return True
    if family_names and len(normalised.split()) >= 2:
        tokens = set(normalised.split())
        if tokens & {name.lower() for name in family_names}:
            return True
    return False


def is_person_noise(value: str, strict: bool = False) -> bool:
    """True if a PERSON candidate is not actually a person's name.

    ``strict`` is used when *admitting* a name to the gazetteer, where a
    false positive is expensive: the name would then be matched literally
    across the whole document. Non-strict mode is used for one-off model hits.
    """
    normalised = _normalise(value)
    if not normalised or len(normalised) < 4:
        return True
    if normalised in PERSON_STOPWORDS:
        return True
    tokens = normalised.split()
    if len(tokens) < 2:
        # Single tokens are too risky: "Sunrise" (a building), "Fiscal",
        # "Orchard" (a locality) all get tagged PERSON by the model.
        return True
    if all(token in PERSON_STOPWORDS for token in tokens):
        return True
    if any(token in {"limited", "ltd", "llp", "trust", "bank"} for token in tokens):
        return True
    if not strict:
        return False

    # -- strict gate ----------------------------------------------------
    if len(tokens) > 5:
        return True
    if any(char.isdigit() for char in value):
        return True
    # Real names in this document are clean word sequences; anything with
    # brackets, slashes or colons is a defined term or a fragment.
    if re.search(r"[():/\\@0-9]", value):
        return True
    if contains_domain_noise(value):
        return True
    if is_defined_term(value):
        return True
    if any(token in PERSON_STOPWORDS for token in tokens):
        return True
    # A corporate-form token means this is an entity, not a person.
    if set(tokens) & LEGAL_ENTITY_MARKERS:
        return True
    # A regulator's name inside the span means the model swallowed a heading,
    # e.g. "Listing SEBI Bhavan".
    if any(token in INSTITUTIONAL_ALLOWLIST for token in tokens):
        return True
    # Real names have at least two substantial tokens; "Gopal Bo" is a
    # fragment left behind by a line break.
    if sum(1 for token in tokens if len(token) >= 3) < 2:
        return True
    # Every token must be capitalised in the source text.
    return not all(
        token[:1].isupper() and token[1:].islower() or token.isupper()
        for token in value.split()
        if token
    )
