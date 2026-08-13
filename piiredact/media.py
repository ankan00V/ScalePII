"""Conservative redaction of raster images embedded in a Word document.

Text extraction is not enough for a privacy tool. A .docx can contain QR
codes, logos, scanned identity cards, signatures, photographs and screenshots;
none of that is visible to a text-only detector. The supplied prospectus does
contain such images, including issuer/intermediary branding and identity-card
scans with direct personal identifiers.

This module therefore replaces every embedded raster image with a neutral
redaction placeholder by default. The replacement happens at the package-part
level, so the existing drawing positions and dimensions stay intact. This is a
deliberately conservative policy: preserving benign images safely would require
OCR and visual classification, neither of which should be allowed to silently
leave a high-risk image in a privacy release.
"""

from __future__ import annotations

from pathlib import Path

from docx.parts.image import ImagePart


_ASSET_DIRECTORY = Path(__file__).resolve().parent.parent / "assets"
_PLACEHOLDER_BY_CONTENT_TYPE = {
    "image/png": _ASSET_DIRECTORY / "redacted-image-placeholder.png",
    "image/jpeg": _ASSET_DIRECTORY / "redacted-image-placeholder.jpeg",
}


def redact_embedded_images(document) -> list[dict[str, str]]:
    """Replace every embedded raster image with a neutral placeholder.

    Returning only the package location and media type keeps the audit trail
    useful without copying image contents or source identities into output.
    Unsupported media types fail closed rather than leaving their contents in
    the release by accident.
    """
    redactions: list[dict[str, str]] = []
    for part in document.part.package.parts:
        if not isinstance(part, ImagePart):
            continue
        placeholder_path = _PLACEHOLDER_BY_CONTENT_TYPE.get(part.content_type)
        if placeholder_path is None:
            raise ValueError(
                "cannot safely redact embedded image with unsupported media type "
                f"{part.content_type!r} at {part.partname}"
            )
        if not placeholder_path.is_file():
            raise FileNotFoundError(
                f"image-redaction placeholder is missing: {placeholder_path}"
            )

        # ``ImagePart`` serialises ``_blob``. Clear its lazily cached image so
        # any later dimension or image access observes the replacement bytes.
        part._blob = placeholder_path.read_bytes()
        part._image = None
        redactions.append(
            {
                "part": str(part.partname),
                "content_type": part.content_type,
                "action": "replaced_with_neutral_placeholder",
            }
        )
    return redactions
