"""Normalize identifiers for hashing. Display values stay separate."""

from __future__ import annotations

import hashlib
import re

from thati.extract import normalize_digits
from thati.schemas import EntityType

SOURCE_EXCERPT_LIMIT = 1000


def excerpt_source(text: str) -> str:
    return text[:SOURCE_EXCERPT_LIMIT]


def hash_source(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_identifier(entity_type: EntityType, value: str) -> str:
    raw = normalize_digits(value).strip()
    if entity_type == "phone":
        return re.sub(r"\D", "", raw)
    if entity_type == "bank_account":
        return re.sub(r"\D", "", raw)
    if entity_type == "email":
        return raw.casefold()
    if entity_type == "url":
        return raw.casefold().rstrip("/")
    if entity_type == "social_handle":
        return raw.casefold().lstrip("@")
    if entity_type == "crypto_wallet":
        return raw.casefold()
    return raw.casefold()


def hash_normalized(entity_type: EntityType, normalized_value: str) -> str:
    material = f"{entity_type}\0{normalized_value}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def hash_identifier(entity_type: EntityType, value: str) -> str:
    return hash_normalized(entity_type, normalize_identifier(entity_type, value))


def mask_identifier(entity_type: EntityType, value: str) -> str:
    text = value.strip()
    if entity_type == "email" and "@" in text:
        local, _, domain = text.partition("@")
        head = local[:1] if local else "*"
        return f"{head}***@{domain}"
    if entity_type == "url":
        if len(text) <= 12:
            return text[:4] + "***"
        return text[:8] + "***" + text[-4:]
    digits = re.sub(r"\D", "", normalize_digits(text))
    if entity_type in {"phone", "bank_account"} and len(digits) >= 6:
        return f"{digits[:2]}{'*' * (len(digits) - 5)}{digits[-3:]}"
    if len(text) <= 4:
        return text[:1] + "***"
    return f"{text[:2]}***{text[-2:]}"
