from uuid import uuid4

import pytest
from pydantic import ValidationError

from thati.schemas import (
    RISK_SCORE_IS_PROBABILITY,
    AnalysisResponse,
    BlacklistMatch,
    EvidenceItem,
    ExtractedEntity,
    FraudAssessment,
    risk_level_for_score,
)

SOURCE = (
    "မင်္ဂလာပါ KBZ ဘဏ်မှ ဖြစ်ပါတယ်။ အကောင့်ပိတ်ပါမည်။ "
    "09-123456789 သို့ ငွေ 50000 ကျပ် လွှဲပြီး OTP ပို့ပေးပါ။ "
    "https://kbz-secure-login.example/otp"
)


def _valid_assessment(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "risk_score": 82,
        "risk_level": "critical",
        "likely_fraud": True,
        "scam_type": "bank_impersonation_sms",
        "myanmar_summary": (
            "ဤစာသည် ဘဏ်အယောင်ဆောင်ပြီး အရေးပေါ်ငွေလွှဲခိုင်းသည့် ပုံစံနှင့် တူသည်။ "
            "လူတစ်ဦးကို ပြစ်မှုကျူးလွန်သူဟု မသတ်မှတ်ပါ။"
        ),
        "english_summary": (
            "This message matches a bank-impersonation pattern that urges an urgent transfer. "
            "This is a screening result, not a finding that a person committed a crime."
        ),
        "evidence": [
            {
                "quote": "အကောင့်ပိတ်ပါမည်",
                "myanmar_explanation": "ခြိမ်းခြောက်ပြီး အရေးပေါ်လုပ်ခိုင်းသည့် စကားလုံး ဖြစ်သည်။",
                "severity": "high",
            },
            {
                "quote": "OTP ပို့ပေးပါ",
                "myanmar_explanation": "ဘဏ်က OTP ပြန်တောင်းလေ့မရှိသောကြောင့် သတိထားသင့်သည်။",
                "severity": "critical",
            },
        ],
        "entities": [
            {
                "type": "phone",
                "exact_value": "09-123456789",
                "myanmar_label": "ဖုန်းနံပါတ်",
                "confidence": 0.94,
                "source_quote": "09-123456789 သို့ ငွေ 50000 ကျပ် လွှဲပြီး",
            },
            {
                "type": "url",
                "exact_value": "https://kbz-secure-login.example/otp",
                "myanmar_label": "လင့်ခ်",
                "confidence": 0.91,
                "source_quote": "https://kbz-secure-login.example/otp",
            },
        ],
        "myanmar_safe_actions": [
            "ငွေမလွှဲမီ တရားဝင်ဘဏ်အက်ပ် သို့မဟုတ် ဘဏ်ဖုန်းနံပါတ်မှသာ စစ်ဆေးပါ။",
            "OTP၊ PIN သို့မဟုတ် စကားဝှက်ကို မည်သူ့ကိုမျှ မပို့ပါနှင့်။",
            "အရေးပေါ်အန္တရာယ်ရှိပါက ဒေသဆိုင်ရာအာဏာပိုင်ထံ ဆက်သွယ်ပါ။",
        ],
        "uncertainty": (
            "This screen cannot confirm who sent the message, whether the number is in use, "
            "or whether a crime occurred."
        ),
        "detected_languages": ["my", "en"],
        "extracted_text": SOURCE,
    }
    payload.update(overrides)
    return payload


def test_risk_score_is_not_a_probability() -> None:
    assert RISK_SCORE_IS_PROBABILITY is False
    schema = FraudAssessment.model_fields["risk_score"].description or ""
    assert "Not a probability" in schema


def test_valid_assessment_and_analysis_response() -> None:
    assessment = FraudAssessment.model_validate(_valid_assessment())
    response = AnalysisResponse(
        analysis_id=uuid4(),
        source_type="text",
        assessment=assessment,
        known_blacklist_matches=[
            BlacklistMatch(
                entity_type="phone",
                masked_display_value="09****789",
                matched=True,
                risk_level="critical",
                reports_count=1,
            )
        ],
    )
    assert response.source_type == "text"
    assert response.assessment.likely_fraud is True
    assert len(response.known_blacklist_matches) == 1


@pytest.mark.parametrize(
    ("score", "level"),
    [(0, "low"), (24, "low"), (25, "medium"), (49, "medium"), (50, "high"), (74, "high"), (75, "critical"), (100, "critical")],
)
def test_risk_level_bands(score: int, level: str) -> None:
    assert risk_level_for_score(score) == level
    assessment = FraudAssessment.model_validate(
        _valid_assessment(risk_score=score, risk_level=level)
    )
    assert assessment.risk_level == level


def test_mismatched_risk_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="does not match screening score"):
        FraudAssessment.model_validate(_valid_assessment(risk_score=82, risk_level="low"))


def test_risk_score_bounds() -> None:
    with pytest.raises(ValidationError):
        FraudAssessment.model_validate(_valid_assessment(risk_score=-1))
    with pytest.raises(ValidationError):
        FraudAssessment.model_validate(_valid_assessment(risk_score=101))


def test_invalid_entity_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExtractedEntity.model_validate(
            {
                "type": "national_id",
                "exact_value": "09-123456789",
                "myanmar_label": "ဖုန်း",
                "confidence": 0.5,
                "source_quote": "09-123456789 သို့",
            }
        )


def test_invalid_risk_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FraudAssessment.model_validate(_valid_assessment(risk_level="severe"))


def test_invented_evidence_quote_is_rejected() -> None:
    with pytest.raises(ValidationError, match="invented"):
        FraudAssessment.model_validate(
            _valid_assessment(
                evidence=[
                    {
                        "quote": "သင့်ကို လိမ်နေသည်",
                        "myanmar_explanation": "မူရင်းစာထဲတွင် မရှိသော စာကြောင်း။",
                        "severity": "high",
                    }
                ]
            )
        )


def test_invented_entity_value_is_rejected() -> None:
    with pytest.raises(ValidationError, match="invented"):
        FraudAssessment.model_validate(
            _valid_assessment(
                entities=[
                    {
                        "type": "phone",
                        "exact_value": "09999999999",
                        "myanmar_label": "ဖုန်းနံပါတ်",
                        "confidence": 0.9,
                        "source_quote": "09999999999",
                    }
                ]
            )
        )


def test_entity_value_must_appear_in_source_quote() -> None:
    with pytest.raises(ValidationError, match="exact_value must appear inside source_quote"):
        ExtractedEntity.model_validate(
            {
                "type": "email",
                "exact_value": "help@example.com",
                "myanmar_label": "အီးမေးလ်",
                "confidence": 0.8,
                "source_quote": "ဆက်သွယ်ရန် ဒီကနေပါ",
            }
        )


def test_uncertainty_is_mandatory() -> None:
    payload = _valid_assessment()
    del payload["uncertainty"]
    with pytest.raises(ValidationError):
        FraudAssessment.model_validate(payload)
    with pytest.raises(ValidationError):
        FraudAssessment.model_validate(_valid_assessment(uncertainty=""))


def test_criminal_declaration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not declare that a person is a criminal"):
        FraudAssessment.model_validate(
            _valid_assessment(english_summary="This person is a criminal who sent a scam SMS.")
        )


def test_unsafe_action_is_rejected() -> None:
    with pytest.raises(ValidationError, match="safe and non-accusatory"):
        FraudAssessment.model_validate(
            _valid_assessment(
                myanmar_safe_actions=["Confront the sender and send money first to verify."]
            )
        )


def test_evidence_item_requires_exact_quote() -> None:
    item = EvidenceItem.model_validate(
        {
            "quote": "OTP ပို့ပေးပါ",
            "myanmar_explanation": "OTP တောင်းခြင်းသည် သတိပေးချက် ဖြစ်နိုင်သည်။",
            "severity": "critical",
        }
    )
    assert item.quote == "OTP ပို့ပေးပါ"
    with pytest.raises(ValidationError):
        EvidenceItem.model_validate(
            {
                "quote": "",
                "myanmar_explanation": "ရှင်းလင်းချက်",
                "severity": "low",
            }
        )
