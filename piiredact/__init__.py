"""PII detection and pseudonymisation for Word documents."""

from .pipeline import detect_only, harvest, redact
from .media import redact_embedded_images
from .spans import Span

__all__ = ["Span", "detect_only", "harvest", "redact", "redact_embedded_images"]
__version__ = "1.0.0"
