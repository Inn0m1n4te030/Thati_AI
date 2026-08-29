"""Live Gemini text screening. SDK import happens only when building a live client."""

from __future__ import annotations

import base64
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from thati.audio import provider_audio_mime
from thati.config import Settings
from thati.errors import ProviderError, ProviderUnavailableError
from thati.extract import detect_languages, extract_contact_entities
from thati.prompts import (
    EVIDENCE_FIRST_SYSTEM_PROMPT,
    IMAGE_SYSTEM_PROMPT,
    IMAGE_USER_PROMPT,
    UNTRUSTED_MESSAGE_WRAPPER,
)
from thati.schemas import ExtractedEntity, FraudAssessment, risk_level_for_score

logger = logging.getLogger("thati.live")

GenerateContent = Callable[..., Any]


def wrap_untrusted_message(text: str) -> str:
    return UNTRUSTED_MESSAGE_WRAPPER.format(message=text)


def live_generate_config() -> dict[str, Any]:
    return {
        "system_instruction": EVIDENCE_FIRST_SYSTEM_PROMPT,
        "response_mime_type": "application/json",
        "response_schema": FraudAssessment,
        "temperature": 0.1,
    }


def live_image_generate_config() -> dict[str, Any]:
    config = live_generate_config()
    config["system_instruction"] = IMAGE_SYSTEM_PROMPT
    return config


def image_generate_contents(file_uri: str, mime_type: str) -> list[dict[str, Any] | str]:
    """Gemini Files API part: file_data.file_uri plus the image-understanding prompt."""
    return [
        {
            "file_data": {
                "file_uri": file_uri,
                "mime_type": mime_type,
            }
        },
        IMAGE_USER_PROMPT,
    ]


TRANSCRIPTION_LANGUAGE_CODES = ["my-MM", "en-US"]
TRANSCRIPTION_VOCABULARY = [
    "KBZPay",
    "KBZ Pay",
    "AYA",
    "Wave Money",
    "OTP",
    "PIN",
    "CVV",
    "account",
    "transfer",
    "အကောင့်",
    "ငွေလွှဲ",
]


def audio_inline_input(data: bytes, mime_type: str) -> list[dict[str, str]]:
    """Inline audio for Gemini 3.5 Transcribe (Interactions API)."""
    return [
        {
            "type": "audio",
            "mime_type": provider_audio_mime(mime_type),
            "data": base64.b64encode(data).decode("ascii"),
        }
    ]


def audio_interaction_input(file_uri: str, mime_type: str | None = None) -> list[dict[str, str]]:
    """Files-API URI form. Prefer audio_inline_input for live audio."""
    item = {"type": "audio", "uri": file_uri}
    if mime_type:
        item["mime_type"] = provider_audio_mime(mime_type)
    return [item]


TRANSCRIBE_ONLY_PROMPT = (
    "ဤအသံသည် မြန်မာဘာသာ (Burmese) ဖြစ်နိုင်ပြီး အင်္ဂလိပ် စကားလုံးများ ရောနေနိုင်သည်။ "
    "ကြားသည့်အတိုင်း စာသားမှတ်တမ်းသာ ရေးပါ။ မြန်မာစာကို မြန်မာစာဖြင့် ထားပါ။ "
    "ဘာသာပြန်ခြင်း၊ အကျဉ်းချုပ်ခြင်း သို့မဟုတ် စစ်ဆေးခြင်း မလုပ်ပါနှင့်။"
)


def live_transcription_config() -> dict[str, Any]:
    return {
        "transcription_config": {
            "language_codes": list(TRANSCRIPTION_LANGUAGE_CODES),
            "mode": {"type": "smart"},
            "custom_vocabulary": list(TRANSCRIPTION_VOCABULARY),
        }
    }


def _parse_transcript(response: Any) -> str:
    for attr in ("output_text", "text"):
        text = getattr(response, attr, None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, str) and parsed.strip():
        return parsed.strip()
    parts: list[str] = []
    for step in getattr(response, "steps", None) or []:
        for content in getattr(step, "content", None) or []:
            text = getattr(content, "text", None)
            if text is None and isinstance(content, dict):
                text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    if parts:
        return "\n".join(parts)
    raise ProviderError("empty_transcript")


def _json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ProviderError("empty_provider_response")
    return payload


def _coerce_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Trust the numeric screening score when the model mislabels risk_level."""
    data = dict(payload)
    score = data.get("risk_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return data
    data["risk_level"] = risk_level_for_score(int(score))
    return data


def _assessment_from_provider_payload(payload: dict[str, Any]) -> FraudAssessment:
    return FraudAssessment.model_validate(_coerce_provider_payload(payload))


def _parse_provider_response(response: Any) -> FraudAssessment:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, FraudAssessment):
        return parsed
    if isinstance(parsed, dict):
        return _assessment_from_provider_payload(parsed)
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        try:
            return _assessment_from_provider_payload(_json_object(text))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("empty_provider_response") from exc
    raise ProviderError("empty_provider_response")


def _merge_entities(
    model_entities: list[ExtractedEntity],
    regex_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    merged: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()
    for entity in [*regex_entities, *model_entities]:
        key = (entity.type, entity.exact_value)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entity)
    return merged


def sanitize_assessment(assessment: FraudAssessment, source_text: str) -> FraudAssessment:
    payload = assessment.model_dump()
    payload["extracted_text"] = source_text
    payload["detected_languages"] = detect_languages(source_text)
    payload["evidence"] = [
        item for item in payload["evidence"] if item["quote"] in source_text
    ]
    payload["entities"] = [
        item
        for item in payload["entities"]
        if item["exact_value"] in source_text and item["source_quote"] in source_text
    ]
    regex_entities = extract_contact_entities(source_text)
    payload["entities"] = [
        entity.model_dump()
        for entity in _merge_entities(
            [ExtractedEntity.model_validate(item) for item in payload["entities"]],
            regex_entities,
        )
    ]
    if not payload["evidence"] and payload["risk_score"] >= 50:
        payload["risk_score"] = 32
    payload["risk_level"] = risk_level_for_score(payload["risk_score"])
    if not str(payload.get("uncertainty") or "").strip():
        payload["uncertainty"] = (
            "Signals are incomplete. This screen cannot confirm the sender, "
            "the destination of funds, or whether a crime occurred."
        )
    return FraudAssessment.model_validate(payload)


class GeminiFraudClient:
    """Same analyze_text interface as MockFraudClient; optional Files API for images."""

    def __init__(
        self,
        *,
        model: str,
        generate_content: GenerateContent,
        files_upload: Callable[..., Any] | None = None,
        files_delete: Callable[..., Any] | None = None,
        transcription_model: str | None = None,
        sdk: Any | None = None,
        create_interaction: Callable[..., Any] | None = None,
    ) -> None:
        self.model = model
        self.transcription_model = transcription_model or "gemini-3.5-transcribe"
        self._generate_content = generate_content
        self._files_upload = files_upload
        self._files_delete = files_delete
        self._create_interaction = create_interaction
        # google-genai Client.__del__ closes httpx even if Files/Models remain.
        # Keep the SDK instance so uploads survive GC and FastAPI request scope.
        self._sdk = sdk

    def analyze_text(self, text: str) -> FraudAssessment:
        try:
            response = self._generate_content(
                model=self.model,
                contents=wrap_untrusted_message(text),
                config=live_generate_config(),
            )
            assessment = _parse_provider_response(response)
            return sanitize_assessment(assessment, text)
        except ProviderError:
            raise
        except Exception as exc:
            logger.exception("Live text analysis failed")
            raise ProviderError("provider_error") from exc

    def analyze_image(self, image_path: Path, mime_type: str) -> FraudAssessment:
        if self._files_upload is None or self._files_delete is None:
            raise ProviderUnavailableError()
        uploaded = None
        try:
            uploaded = self._files_upload(
                file=str(image_path),
                config={"mime_type": mime_type},
            )
            uri = getattr(uploaded, "uri", None)
            if not uri:
                raise ProviderError("provider_error")
            response = self._generate_content(
                model=self.model,
                contents=image_generate_contents(str(uri), mime_type),
                config=live_image_generate_config(),
            )
            assessment = _parse_provider_response(response)
            return sanitize_assessment(assessment, assessment.extracted_text)
        except ProviderError:
            raise
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            logger.exception("Live image analysis failed")
            raise ProviderError("provider_error") from exc
        finally:
            if uploaded is not None and self._files_delete is not None:
                try:
                    self._files_delete(name=uploaded.name)
                except Exception:
                    logger.exception("Failed to delete Gemini file %s", getattr(uploaded, "name", "?"))

    def transcribe_audio(self, audio_path: Path, mime_type: str) -> str:
        data = Path(audio_path).read_bytes()
        if not data:
            raise ProviderError("empty_transcript")
        provider_mime = provider_audio_mime(mime_type)
        try:
            return self._transcribe_bytes(data, provider_mime)
        except ProviderError:
            raise
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            logger.exception("Live transcription failed")
            raise ProviderError("provider_error") from exc

    def _transcribe_bytes(self, data: bytes, mime_type: str) -> str:
        if self._create_interaction is not None:
            try:
                interaction = self._create_interaction(
                    model=self.transcription_model,
                    input=audio_inline_input(data, mime_type),
                    generation_config=live_transcription_config(),
                )
                return _parse_transcript(interaction)
            except ProviderError:
                logger.warning("Interactions transcript empty; trying understanding model")
            except Exception:
                logger.exception("Interactions transcription failed; trying understanding model")
        return self._transcribe_with_understanding_model(data, mime_type)

    def _transcribe_with_understanding_model(self, data: bytes, mime_type: str) -> str:
        if self._sdk is not None:
            from google.genai import types

            response = self._sdk.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=data, mime_type=mime_type),
                    TRANSCRIBE_ONLY_PROMPT,
                ],
                config={"temperature": 0.1},
            )
            return _parse_transcript(response)
        response = self._generate_content(
            model=self.model,
            contents=[
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(data).decode("ascii"),
                    }
                },
                TRANSCRIBE_ONLY_PROMPT,
            ],
            config={"temperature": 0.1},
        )
        return _parse_transcript(response)

    def analyze_audio(self, audio_path: Path, mime_type: str) -> FraudAssessment:
        transcript = self.transcribe_audio(audio_path, mime_type)
        return self.analyze_text(transcript)


def build_live_client(
    settings: Settings,
    generate_content: GenerateContent | None = None,
) -> GeminiFraudClient:
    if generate_content is None:
        if not settings.gemini_api_key.strip():
            raise ProviderUnavailableError()
        from google import genai
        from google.genai import types

        sdk = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=settings.gemini_timeout_ms),
        )
        create_interaction = getattr(getattr(sdk, "interactions", None), "create", None)
        return GeminiFraudClient(
            model=settings.gemini_model,
            transcription_model=settings.transcription_model,
            generate_content=sdk.models.generate_content,
            files_upload=sdk.files.upload,
            files_delete=sdk.files.delete,
            create_interaction=create_interaction,
            sdk=sdk,
        )
    return GeminiFraudClient(
        model=settings.gemini_model,
        generate_content=generate_content,
    )
