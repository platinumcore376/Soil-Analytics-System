"""Text-to-speech proxy (Weeks 5-6 — Module 3).

Documentation requirement (page 2):
    "integrate Sarvam AI for reading AI-generated diagnostic results and recommendations
     aloud in the farmer's regional language"

WHY A SERVER-SIDE PROXY
-----------------------
The Sarvam API key must never reach the browser. A PWA ships its JavaScript to every
device, so a key embedded client-side is a published key. The frontend posts text here and
receives audio bytes; the key stays in the server's environment.

DEGRADATION
-----------
When `SARVAM_API_KEY` is unset this returns `503` with a machine-readable `reason`, and the
frontend falls back to the browser's Web Speech API. That fallback is why read-aloud works
today without a key — but it depends on device-installed voices, which for Hindi, Kannada
and especially Telugu are often absent on the low-end Android phones this project targets.
Sarvam is the path to a voice that is actually present.

The endpoint is unauthenticated-adjacent by design: it requires a signed-in user (TTS costs
money per call, so it must not be an open relay) but does not touch the database.
"""
from __future__ import annotations

import base64
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import CurrentUser
from app.config import settings

router = APIRouter(tags=["tts"])

logger = logging.getLogger(__name__)

# Sarvam's Bulbul TTS speaker codes per language. Sarvam covers the Indian languages this
# project ships; `en-IN` keeps an Indian-English accent rather than US English.
SARVAM_LANGUAGE_CODES = {
    "en": "en-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "te": "te-IN",
}

# Sarvam rejects overly long input, and a farmer will not listen to more than a paragraph.
MAX_TTS_CHARS = 1500


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    language: str = Field(default="en", pattern="^(en|hi|kn|te)$")


@router.post("/tts", response_class=Response)
async def synthesise(payload: TTSRequest, user: CurrentUser) -> Response:
    """Synthesise `text` to speech in `language` and return the audio bytes.

    Returns `audio/wav` on success. The frontend checks the `content-type` starts with
    `audio` before playing, so any error shape here safely triggers its fallback.
    """
    if not settings.sarvam_api_key:
        # 503 (not 500): the service is unconfigured, not broken. The client treats any
        # non-audio response as "use Web Speech instead".
        raise HTTPException(
            status_code=503,
            detail={
                "reason": "tts_not_configured",
                "message": (
                    "Sarvam TTS is not configured. Set SARVAM_API_KEY to enable "
                    "server-side speech; the app falls back to on-device synthesis."
                ),
            },
        )

    body = {
        "inputs": [payload.text],
        "target_language_code": SARVAM_LANGUAGE_CODES[payload.language],
        "speaker": settings.sarvam_speaker,
        "model": settings.sarvam_model,
        # Slightly slower than default: these are dosage figures and field advice, not prose.
        "pace": 0.9,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.sarvam_timeout_seconds) as client:
            response = await client.post(
                f"{settings.sarvam_base_url.rstrip('/')}/text-to-speech",
                json=body,
                headers={"api-subscription-key": settings.sarvam_api_key},
            )
    except httpx.TimeoutException as exc:
        # Rural connectivity is the norm here. A slow upstream must not hang the request.
        raise HTTPException(
            status_code=504,
            detail={"reason": "tts_timeout", "message": "Speech service timed out."},
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Sarvam TTS request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"reason": "tts_unreachable", "message": "Speech service unreachable."},
        ) from exc

    if response.status_code != 200:
        # Log the upstream body for diagnosis but do not forward it — it may name the key.
        logger.warning(
            "Sarvam TTS returned %s: %s", response.status_code, response.text[:300]
        )

        # Distinguish the causes. Collapsing everything into 502 "Bad Gateway" was wrong:
        # the first real call returned 402 "No credits available", and reporting a billing
        # state as an upstream outage sends whoever is debugging it to the wrong place.
        #
        # Every branch still returns a non-audio response, so the client's fallback to Web
        # Speech is unchanged — what differs is whether the reason is actionable.
        if response.status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail={
                    "reason": "tts_auth_rejected",
                    "message": (
                        "Sarvam rejected the API key. Check SARVAM_API_KEY is current and "
                        "has text-to-speech access."
                    ),
                },
            )
        if response.status_code in (402, 429):
            # 402 = out of credits, 429 = rate limited. Both are quota, both resolve without
            # a code change, and both should say so plainly.
            raise HTTPException(
                status_code=503,
                detail={
                    "reason": "tts_quota_exhausted",
                    "message": (
                        "Sarvam has no credits available or the rate limit was hit. Voice "
                        "falls back to on-device speech until the account is topped up."
                    ),
                    "upstream_status": response.status_code,
                },
            )
        raise HTTPException(
            status_code=502,
            detail={
                "reason": "tts_upstream_error",
                "message": f"Speech service returned {response.status_code}.",
            },
        )

    # Sarvam returns base64 WAV in `audios[0]`. Decode server-side so the client gets a
    # plain audio blob it can hand straight to `new Audio()`.
    try:
        audios = response.json().get("audios") or []
        if not audios:
            raise ValueError("no audio in response")
        audio_bytes = base64.b64decode(audios[0])
    except Exception as exc:  # noqa: BLE001 - any malformed shape is one failure mode
        logger.warning("Could not decode Sarvam TTS response: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"reason": "tts_bad_response", "message": "Malformed speech response."},
        ) from exc

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            # Same text in the same language always yields the same audio, and a farmer
            # re-reads their report. Let the browser and service worker cache it.
            "Cache-Control": "private, max-age=86400",
        },
    )
