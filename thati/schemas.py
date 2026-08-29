"""Evidence-first fraud screening data contract.

Rules encoded here:
- risk_score is a screening indicator, not a probability.
- Evidence quotes and entity values must appear in extracted_text; nothing may be invented.
- Assessments must not declare that a person is a criminal.
- uncertainty is required.
- Recommended actions must be safe and non-accusatory.
"""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

EntityType = Literal[
    "phone",
    "bank_account",
    "email",
    "url",
    "social_handle",
    "crypto_wallet",
    "other",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
Severity = Literal["low", "medium", "high", "critical"]
SourceType = Literal["text", "screenshot", "voice"]

RISK_SCORE_IS_PROBABILITY = False

_CRIMINAL_CLAIM = re.compile(
    r"("
    r"is a criminal|are criminals|guilty of (?:fraud|a crime)|"
    r"this person (?:is|was) a (?:scammer|criminal)|"
    r"this individual (?:is|was) a (?:scammer|criminal)|"
    r"သူက ရာဇဝတ်သား|ဒီလူက ရာဇဝတ်သား|ပြစ်မှုကျူးလွန်သူဖြစ်"
    r")",
    re.IGNORECASE,
)
_UNSAFE_ACTION = re.compile(
    r"("
    r"confront the (?:sender|scammer|person)|"
    r"go to their (?:house|address|office)|"
    r"send (?:money|otp|password|pin)|"
    r"transfer (?:first|now|immediately)|"
    r"share (?:otp|password|pin)|"
    r"revenge|doxx|"
    r"ငွေအရင်လွှဲ|otp ပို့ပေး"
    r")",
    re.IGNORECASE,
)


def risk_level_for_score(score: int) -> RiskLevel:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


def _require_substring(needle: str, haystack: str, *, field_name: str) -> None:
    if needle not in haystack:
        raise ValueError(
            f"{field_name} must be an exact substring of extracted_text; invented text is not allowed"
        )


def _reject_criminal_claim(text: str, *, field_name: str) -> str:
    if _CRIMINAL_CLAIM.search(text):
        raise ValueError(
            f"{field_name} must not declare that a person is a criminal"
        )
    return text


def _reject_unsafe_action(text: str) -> str:
    if _UNSAFE_ACTION.search(text):
        raise ValueError("recommended actions must be safe and non-accusatory")
    return text


class EvidenceItem(BaseModel):
    quote: str = Field(
        ...,
        min_length=1,
        description="Exact quote copied from the user input. Must not be paraphrased.",
    )
    myanmar_explanation: str = Field(
        ...,
        min_length=1,
        description="Why this quote is suspicious, written in Myanmar.",
    )
    severity: Severity


class ExtractedEntity(BaseModel):
    type: EntityType
    exact_value: str = Field(
        ...,
        min_length=1,
        description="Identifier exactly as it appears in the input.",
    )
    myanmar_label: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_quote: str = Field(
        ...,
        min_length=1,
        description="Surrounding quote from the input that contains exact_value.",
    )

    @model_validator(mode="after")
    def exact_value_in_source_quote(self) -> ExtractedEntity:
        if self.exact_value not in self.source_quote:
            raise ValueError("exact_value must appear inside source_quote")
        return self


class FraudAssessment(BaseModel):
    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description=(
            "Screening indicator from 0-100. Not a probability, not a legal finding, "
            "and not a statement that a person committed a crime."
        ),
    )
    risk_level: RiskLevel
    likely_fraud: bool = Field(
        ...,
        description="Likely-fraud screening indicator for this message, not a verdict about a person.",
    )
    scam_type: str = Field(..., min_length=1)
    myanmar_summary: str = Field(..., min_length=1)
    english_summary: str = Field(..., min_length=1)
    evidence: list[EvidenceItem]
    entities: list[ExtractedEntity]
    myanmar_safe_actions: list[str] = Field(..., min_length=1)
    uncertainty: str = Field(
        ...,
        min_length=1,
        description="Mandatory statement of what the model cannot confirm.",
    )
    detected_languages: list[str] = Field(..., min_length=1)
    extracted_text: str = Field(
        ...,
        min_length=1,
        description="Source text that was screened. Evidence and entities must occur in this string.",
    )

    @field_validator("myanmar_summary", "english_summary")
    @classmethod
    def summaries_are_non_accusatory(cls, value: str) -> str:
        return _reject_criminal_claim(value, field_name="summary")

    @field_validator("myanmar_safe_actions")
    @classmethod
    def actions_are_safe(cls, actions: list[str]) -> list[str]:
        cleaned: list[str] = []
        for action in actions:
            if not action.strip():
                raise ValueError("safe actions must not be empty")
            _reject_criminal_claim(action, field_name="myanmar_safe_actions")
            cleaned.append(_reject_unsafe_action(action))
        return cleaned

    @model_validator(mode="after")
    def score_matches_level(self) -> FraudAssessment:
        expected = risk_level_for_score(self.risk_score)
        if self.risk_level != expected:
            raise ValueError(
                f"risk_level {self.risk_level!r} does not match screening score "
                f"{self.risk_score} (expected {expected!r})"
            )
        return self

    @model_validator(mode="after")
    def nothing_invented(self) -> FraudAssessment:
        source = self.extracted_text
        for item in self.evidence:
            _require_substring(item.quote, source, field_name="evidence.quote")
            _reject_criminal_claim(
                item.myanmar_explanation,
                field_name="evidence.myanmar_explanation",
            )
        for entity in self.entities:
            _require_substring(
                entity.exact_value,
                source,
                field_name="entities.exact_value",
            )
            _require_substring(
                entity.source_quote,
                source,
                field_name="entities.source_quote",
            )
        return self


class BlacklistMatch(BaseModel):
    entity_type: EntityType
    exact_value: str = Field(..., min_length=1)
    normalized_value: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    analysis_id: UUID
    source_type: SourceType
    assessment: FraudAssessment
    known_blacklist_matches: list[BlacklistMatch] = Field(default_factory=list)
