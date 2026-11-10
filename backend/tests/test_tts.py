"""The Sarvam TTS proxy — fully mocked, so NO Sarvam credits are ever spent.

Each upstream failure mode maps to a distinct machine-readable `reason`; the
frontend keys its fallback messaging off these, so they are contract, not
implementation detail.
"""
import base64

import app.routers.tts as tts_module
from app.config import settings


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def _fake_async_client(response):
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            return response

    return _Client


def test_tts_requires_auth(client):
    assert client.post("/tts", json={"text": "hello"}).status_code == 401


def test_unconfigured_key_degrades_cleanly(client, make_user):
    u = make_user()
    r = client.post("/tts", json={"text": "hello"}, headers=u["headers"])
    assert r.status_code == 503
    assert r.json()["detail"]["reason"] == "tts_not_configured"


def test_overlong_text_rejected_before_spending_money(client, make_user):
    u = make_user()
    r = client.post(
        "/tts",
        json={"text": "x" * (tts_module.MAX_TTS_CHARS + 1)},
        headers=u["headers"],
    )
    assert r.status_code == 422


def test_success_returns_decoded_wav(client, make_user, monkeypatch):
    u = make_user()
    wav = b"RIFF....WAVEfmt fake-audio-bytes"
    fake = _FakeResponse(200, {"audios": [base64.b64encode(wav).decode()]})
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-key-for-test")
    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _fake_async_client(fake))

    r = client.post("/tts", json={"text": "నమస్కారం", "language": "te"}, headers=u["headers"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("audio/wav")
    assert r.content == wav  # base64 decoded server-side, byte-exact


def test_out_of_credits_reports_quota_not_gateway(client, make_user, monkeypatch):
    """402 from Sarvam is a billing state, not an outage — the reason must say so."""
    u = make_user()
    fake = _FakeResponse(402, text="No credits available")
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-key-for-test")
    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _fake_async_client(fake))

    r = client.post("/tts", json={"text": "hello"}, headers=u["headers"])
    assert r.status_code == 503
    assert r.json()["detail"]["reason"] == "tts_quota_exhausted"


def test_rejected_key_reports_auth(client, make_user, monkeypatch):
    u = make_user()
    fake = _FakeResponse(403, text="invalid key")
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-key-for-test")
    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _fake_async_client(fake))

    r = client.post("/tts", json={"text": "hello"}, headers=u["headers"])
    assert r.status_code == 502
    assert r.json()["detail"]["reason"] == "tts_auth_rejected"


def test_malformed_upstream_body_is_bad_response(client, make_user, monkeypatch):
    u = make_user()
    fake = _FakeResponse(200, {"audios": []})  # 200 but no audio
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-key-for-test")
    monkeypatch.setattr(tts_module.httpx, "AsyncClient", _fake_async_client(fake))

    r = client.post("/tts", json={"text": "hello"}, headers=u["headers"])
    assert r.status_code == 502
    assert r.json()["detail"]["reason"] == "tts_bad_response"


def test_invalid_language_rejected(client, make_user):
    u = make_user()
    r = client.post("/tts", json={"text": "hi", "language": "fr"}, headers=u["headers"])
    assert r.status_code == 422
