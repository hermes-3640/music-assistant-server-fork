"""Tests for the LRCLIB metadata provider."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError
from music_assistant_models.errors import MusicAssistantError

from music_assistant.helpers.throttle_retry import ThrottlerManager
from music_assistant.providers.lrclib import SUPPORTED_FEATURES, LrclibProvider
from tests.common import use_real_create_task


@pytest.fixture
def provider() -> LrclibProvider:
    """Return an LrclibProvider with mocked dependencies and a cold cache."""
    mass = AsyncMock()
    mass.http_session = MagicMock()
    # force a cache miss so the wrapped fetch always runs
    mass.cache.get_with_freshness = AsyncMock(return_value=(None, False, False))
    use_real_create_task(mass)
    manifest = MagicMock()
    manifest.domain = "lrclib"
    config = MagicMock()
    config.get_value.return_value = "GLOBAL"
    prov = LrclibProvider(mass, manifest, config, SUPPORTED_FEATURES)
    prov.api_url = "https://lrclib.net/api"
    # retry_attempts=1 keeps the transient-error test fast (no backoff sleeps)
    prov.throttler = ThrottlerManager(rate_limit=1, period=1, retry_attempts=1)
    return prov


def _response_cm(*, response: MagicMock | None = None, exc: Exception | None = None) -> MagicMock:
    """Build a fake async context manager mimicking aiohttp's session.get()."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response, side_effect=exc)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_get_data_returns_none_when_not_found(provider: LrclibProvider) -> None:
    """A 404 means there are genuinely no lyrics, so None is returned (and cached)."""
    response = MagicMock()
    response.status = 404
    response.raise_for_status = MagicMock()
    provider.mass.http_session.get = MagicMock(  # type: ignore[method-assign]
        return_value=_response_cm(response=response)
    )

    assert await provider._get_data(track_name="Song", artist_name="Artist") is None


async def test_get_data_propagates_transient_error(provider: LrclibProvider) -> None:
    """A network failure surfaces as a MusicAssistantError instead of being cached as 'no lyrics'."""
    provider.mass.http_session.get = MagicMock(  # type: ignore[method-assign]
        return_value=_response_cm(exc=ClientError("network down"))
    )

    with pytest.raises(MusicAssistantError):
        await provider._get_data(track_name="Song", artist_name="Artist")


async def test_get_data_keeps_underlying_error_in_message(
    provider: LrclibProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """The retry log keeps the underlying cause, so an upstream fault is diagnosable."""
    provider.mass.http_session.get = MagicMock(  # type: ignore[method-assign]
        return_value=_response_cm(exc=ClientError("network down"))
    )
    caplog.set_level(logging.INFO)

    with pytest.raises(MusicAssistantError):
        await provider._get_data(track_name="Song", artist_name="Artist")

    assert any("network down" in record.getMessage() for record in caplog.records), [
        record.getMessage() for record in caplog.records
    ]


async def test_get_data_honours_server_retry_after(
    provider: LrclibProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 429 backs off for at least lrclib.net's Retry-After instead of a guessed delay."""
    response = MagicMock()
    response.status = 429
    response.headers = {"Retry-After": "42"}
    response.raise_for_status = MagicMock()
    provider.mass.http_session.get = MagicMock(  # type: ignore[method-assign]
        return_value=_response_cm(response=response)
    )
    # two attempts is enough to observe the backoff the retry helper chooses
    provider.throttler = ThrottlerManager(rate_limit=1, period=1, retry_attempts=2)
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    # patch by dotted path: mypy rejects attribute access to a module's
    # non-exported `asyncio` import
    monkeypatch.setattr("music_assistant.helpers.throttle_retry.asyncio.sleep", fake_sleep)

    with pytest.raises(MusicAssistantError):
        await provider._get_data(track_name="Song", artist_name="Artist")

    assert sleeps, "no backoff sleep was taken before retrying a 429"
    # Retry-After (42s) is a floor; the helper may add jitter above it
    assert any(42.0 <= delay <= 47.0 for delay in sleeps), sleeps
