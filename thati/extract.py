"""Deterministic identifier extraction. Display values stay as in the source text."""

from __future__ import annotations

import re

from thati.schemas import ExtractedEntity

MYANMAR_DIGIT_TO_ARABIC = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")

PHONE_RE = re.compile(
    r"(?<![\d၀-၉])((?:09|၀၉)(?:[\- ]?[\d၀-၉]){6,10})(?![\d၀-၉])"
)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
EMAIL_RE = re.compile(
    r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}",
    re.IGNORECASE,
)


def normalize_digits(value: str) -> str:
    """Map Myanmar digits to Arabic digits for matching only."""
    return value.translate(MYANMAR_DIGIT_TO_ARABIC)


def detect_languages(text: str) -> list[str]:
    languages: list[str] = []
    if re.search(r"[\u1000-\u109F]", text):
        languages.append("my")
    if re.search(r"[A-Za-z]", text):
        languages.append("en")
    return languages or ["und"]


def _source_quote(text: str, start: int, end: int) -> str:
    left = max(0, start - 8)
    right = min(len(text), end + 8)
    return text[left:right]


def extract_contact_entities(text: str) -> list[ExtractedEntity]:
    found: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()

    def add(entity: ExtractedEntity) -> None:
        key = (entity.type, normalize_digits(entity.exact_value).lower())
        if key in seen:
            return
        seen.add(key)
        found.append(entity)

    for match in URL_RE.finditer(text):
        value = match.group(0).rstrip(".,;:!?")
        add(
            ExtractedEntity(
                type="url",
                exact_value=value,
                myanmar_label="လင့်ခ်",
                confidence=0.99,
                source_quote=_source_quote(text, match.start(), match.start() + len(value)),
            )
        )
    for match in EMAIL_RE.finditer(text):
        value = match.group(0)
        add(
            ExtractedEntity(
                type="email",
                exact_value=value,
                myanmar_label="အီးမေးလ်",
                confidence=0.99,
                source_quote=_source_quote(text, match.start(), match.end()),
            )
        )
    for match in PHONE_RE.finditer(text):
        value = match.group(1).strip()
        add(
            ExtractedEntity(
                type="phone",
                exact_value=value,
                myanmar_label="ဖုန်းနံပါတ်",
                confidence=0.98,
                source_quote=_source_quote(text, match.start(), match.end()),
            )
        )
    return found
