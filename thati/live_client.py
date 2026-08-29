"""Live Gemini text screening. SDK import happens only when building a live client."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


def _parse_provider_response(response: Any) -> FraudAssessment:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, FraudAssessment):
        return parsed
    if isinstance(parsed, dict):
        return FraudAssessment.model_validate(parsed)
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return FraudAssessment.model_validate_json(text)
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
    ) -> None:
        self.model = model
        self._generate_content = generate_content
        self._files_upload = files_upload
        self._files_delete = files_delete

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
        generate_content = sdk.models.generate_content
        files_upload = sdk.files.upload
        files_delete = sdk.files.delete
        return GeminiFraudClient(
            model=settings.gemini_model,
            generate_content=generate_content,
            files_upload=files_upload,
            files_delete=files_delete,
        )
    return GeminiFraudClient(
        model=settings.gemini_model,
        generate_content=generate_content,
    )
