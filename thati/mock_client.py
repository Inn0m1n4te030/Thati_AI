"""Deterministic mock screening. No external SDKs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from thati.extract import detect_languages, extract_contact_entities
from thati.schemas import EvidenceItem, FraudAssessment, Severity, risk_level_for_score

SAFE_ACTIONS = [
    "OTP၊ PIN သို့မဟုတ် စကားဝှက်ကို မည်သူ့ကိုမျှ မပို့ပါနှင့်။",
    "မသိသောလင့်ခ်ကို မနှိပ်ပါနှင့်။ တရားဝင်အက်ပ် သို့မဟုတ် သိထားသော ဖုန်းနံပါတ်မှသာ စစ်ဆေးပါ။",
    "ငွေမလွှဲမီ စောင့်ဆိုင်းပြီး သီးခြားလမ်းကြောင်းမှ အတည်ပြုပါ။",
    "အရေးပေါ်အန္တရာယ်ရှိပါက ဒေသဆိုင်ရာအာဏာပိုင်ထံ ဆက်သွယ်ပါ။",
]

UNCERTAINTY = (
    "ဤစစ်ဆေးမှုသည် စာသားပုံစံကိုသာ ကြည့်သည်။ ပေးပို့သူ၊ အကောင့်ပိုင်ရှင်၊ "
    "သို့မဟုတ် ပြစ်မှုဖြစ်ပွားမှုကို အတည်ပြုနိုင်ခြင်း မရှိပါ။"
)


@dataclass(frozen=True)
class SignalPattern:
    category: str
    severity: Severity
    explanation: str
    pattern: re.Pattern[str]


SIGNALS: tuple[SignalPattern, ...] = (
    SignalPattern(
        "credential",
        "critical",
        "OTP တောင်းခြင်းသည် အကောင့်ထိန်းချုပ်မှု လုယူသည့် ပုံစံဖြစ်နိုင်သည်။",
        re.compile(r"OTP|otp|အိုတီပီ"),
    ),
    SignalPattern(
        "credential",
        "critical",
        "PIN တောင်းခြင်းကို တရားဝင်ဘဏ်က ချတ်မှ မတောင်းလေ့ရှိပါ။",
        re.compile(r"\bPIN\b|\bpin\b|ပင်နံပါတ်"),
    ),
    SignalPattern(
        "credential",
        "critical",
        "စကားဝှက်တောင်းခြင်းသည် အကောင့်ခိုးယူရန် သုံးလေ့ရှိသည်။",
        re.compile(r"password|Password|စကားဝှက်|ပါ့စ်ဝဒ်|ပါစ်ဝဒ်", re.IGNORECASE),
    ),
    SignalPattern(
        "pressure",
        "high",
        "အရေးပေါ်ကြောင်း ဖိအားပေးခြင်းသည် ဆုံးဖြတ်ချက်မြန်အောင် လုပ်သည့် ပုံစံဖြစ်နိုင်သည်။",
        re.compile(r"urgent|immediately|အရေးပေါ်|ချက်ချင်း", re.IGNORECASE),
    ),
    SignalPattern(
        "pressure",
        "high",
        "အကောင့်ပိတ်မည်ဟု ခြိမ်းခြောက်ခြင်းသည် သတိထားရမည့် ပုံစံဖြစ်သည်။",
        re.compile(r"account clos(?:e|ed|ure)|အကောင့် ?ပိတ်|အကောင့် ?ပိတ်", re.IGNORECASE),
    ),
    SignalPattern(
        "money",
        "high",
        "ငွေလွှဲခိုင်းခြင်းကို သီးခြားလမ်းကြောင်းမှ အတည်ပြုသင့်သည်။",
        re.compile(r"\btransfer\b|send money|ငွေ ?လွှဲ|လွှဲပြီး", re.IGNORECASE),
    ),
    SignalPattern(
        "return",
        "high",
        "အမြတ်အာမခံခြင်းသည် ရင်းနှီးမြှုပ်နှံမှု လိမ်လည်ပုံစံတွင် တွေ့ရတတ်သည်။",
        re.compile(
            r"guaranteed return|100%\s*profit|အာမခံအမြတ်|အမြတ်သေချာ|အရှုံးမရှိ",
            re.IGNORECASE,
        ),
    ),
    SignalPattern(
        "link",
        "medium",
        "မသိသောလင့်ခ် သို့မဟုတ် နှိပ်ခိုင်းသော လင့်ခ်ကို သတိထားပါ။",
        re.compile(r"click here|bit\.ly|tinyurl|လင့်ခ်|လင့်ခ်|နှိပ်ပါ", re.IGNORECASE),
    ),
)


def _score_from_signals(
    categories: set[str],
    has_url: bool,
) -> tuple[int, str, bool]:
    """High or critical only when concrete combined signals exist."""
    credential = "credential" in categories
    pressure = "pressure" in categories
    money = "money" in categories
    promised_return = "return" in categories
    link = "link" in categories or has_url

    if credential and (money or pressure or link):
        return 82, "otp_phishing", True
    if promised_return and (money or link or pressure):
        return 70, "investment_scam", True
    if credential:
        return 68, "credential_request", True
    if (pressure and money) or (link and (pressure or money)):
        return 62, "urgent_payment", True
    if promised_return:
        return 55, "investment_pitch", True
    if categories or has_url:
        return 32, "weak_signal", False
    return 8, "none", False


SYNTHETIC_SCREENSHOT_TEXT = (
    "KBZ ဘဏ်\n"
    "အကောင့်ပိတ်ပါမည်။ OTP ပို့ပေးပါ။\n"
    "09-123456789\n"
    "https://kbz-secure-login.example/otp"
)


SYNTHETIC_VOICE_TRANSCRIPT = (
    "မင်္ဂလာပါ KBZPay မှ ဖြစ်ပါတယ်။ အကောင့်ပိတ်ပါမည်။ "
    "Wave Money သို့ ငွေလွှဲပြီး OTP နှင့် PIN ပို့ပေးပါ။ "
    "transfer 09-123456789"
)


class MockFraudClient:
    def analyze_image(self, image_path: object, mime_type: str) -> FraudAssessment:
        """Deterministic screenshot result. Pixels are not interpreted in mock mode."""
        del image_path, mime_type
        return self.analyze_text(SYNTHETIC_SCREENSHOT_TEXT)

    def analyze_audio(self, audio_path: object, mime_type: str) -> FraudAssessment:
        """Deterministic fictional Myanmar transcript. Audio bytes are not decoded."""
        del audio_path, mime_type
        return self.analyze_text(SYNTHETIC_VOICE_TRANSCRIPT)

    def analyze_text(self, text: str) -> FraudAssessment:
        evidence: list[EvidenceItem] = []
        seen_quotes: set[str] = set()
        categories: set[str] = set()

        for signal in SIGNALS:
            for match in signal.pattern.finditer(text):
                quote = match.group(0)
                if quote in seen_quotes:
                    continue
                seen_quotes.add(quote)
                categories.add(signal.category)
                evidence.append(
                    EvidenceItem(
                        quote=quote,
                        myanmar_explanation=signal.explanation,
                        severity=signal.severity,
                    )
                )

        entities = extract_contact_entities(text)
        has_url = any(entity.type == "url" for entity in entities)
        if has_url:
            for entity in entities:
                if entity.type != "url" or entity.exact_value in seen_quotes:
                    continue
                seen_quotes.add(entity.exact_value)
                evidence.append(
                    EvidenceItem(
                        quote=entity.exact_value,
                        myanmar_explanation="မသိသောဝဘ်လင့်ခ် ပါနေသည်။ တရားဝင်ဆိုက်နှင့် မတိုက်ဆိုင်မီ မနှိပ်ပါနှင့်။",
                        severity="high",
                    )
                )

        score, scam_type, likely_fraud = _score_from_signals(categories, has_url)
        level = risk_level_for_score(score)
        languages = detect_languages(text)

        if likely_fraud:
            myanmar_summary = (
                "ဤစာတွင် သတိထားရမည့် တောင်းဆိုချက် သို့မဟုတ် ဖိအားပေးသည့် ပုံစံ တွေ့ရသည်။ "
                "လူတစ်ဦးကို ပြစ်မှုကျူးလွန်သူဟု မသတ်မှတ်ပါ။ စာသားပုံစံကိုသာ စစ်ဆေးထားသည်။"
            )
            english_summary = (
                "This message contains concrete screening signals such as credential, "
                "payment, urgency, or link patterns. This is not a finding that a person "
                "committed a crime."
            )
        else:
            myanmar_summary = (
                "ခိုင်မာသော လိမ်လည်ပုံစံ ပေါင်းစပ်မှု မတွေ့သေးပါ။ သို့သော် မသေချာလျှင် "
                "ငွေ၊ OTP သို့မဟုတ် စကားဝှက် မပို့ပါနှင့်။"
            )
            english_summary = (
                "No combined concrete fraud signals were found. This screening score is "
                "an indicator, not a probability and not a personal accusation."
            )

        return FraudAssessment(
            risk_score=score,
            risk_level=level,
            likely_fraud=likely_fraud,
            scam_type=scam_type,
            myanmar_summary=myanmar_summary,
            english_summary=english_summary,
            evidence=evidence,
            entities=entities,
            myanmar_safe_actions=list(SAFE_ACTIONS),
            uncertainty=UNCERTAINTY,
            detected_languages=languages,
            extracted_text=text,
        )
