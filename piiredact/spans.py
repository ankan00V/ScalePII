"""Span model and overlap resolution.

Every detector speaks the same language: it takes a string and returns
``Span`` objects with character offsets into that string. Everything
downstream (conflict resolution, fake substitution, evaluation) operates on
spans alone, so detectors stay independent of each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Span:
    """A single detected PII mention inside one block of text."""

    start: int
    end: int
    text: str
    entity_type: str
    detector: str
    #: Higher wins when two spans overlap. Deterministic detectors (regex on
    #: a rigidly structured value like an email) outrank statistical ones.
    priority: int = 0

    def __len__(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end

    def as_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "entity_type": self.entity_type,
            "detector": self.detector,
        }


def resolve_overlaps(spans: Iterable[Span]) -> list[Span]:
    """Collapse overlapping spans down to one winner per region of text.

    Detectors are intentionally allowed to disagree — an address regex and
    spaCy's ORG model will both fire on "Orchard Society, Example City". We
    settle it here rather than in the detectors so that adding a new detector
    never requires touching an existing one.

    Ranking, in order: explicit priority, then longer match, then leftmost.
    """
    ordered = sorted(spans, key=lambda s: (-s.priority, -len(s), s.start))
    kept: list[Span] = []
    for span in ordered:
        if any(span.overlaps(k) for k in kept):
            continue
        kept.append(span)
    return sorted(kept, key=lambda s: s.start)


def apply_spans(text: str, replacements: list[tuple[Span, str]]) -> str:
    """Rewrite ``text``, substituting each span with its replacement.

    Applied right-to-left so that earlier offsets stay valid as we go.
    """
    out = text
    for span, fake in sorted(replacements, key=lambda p: p[0].start, reverse=True):
        out = out[: span.start] + fake + out[span.end :]
    return out


@dataclass
class DetectionStats:
    """Per-entity-type tallies, used for the run summary in the report."""

    counts: dict[str, int] = field(default_factory=dict)

    def add(self, entity_type: str, n: int = 1) -> None:
        self.counts[entity_type] = self.counts.get(entity_type, 0) + n

    def total(self) -> int:
        return sum(self.counts.values())
