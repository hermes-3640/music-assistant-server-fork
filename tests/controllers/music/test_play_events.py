"""
Tests for the play_events table: per-play start, finish, and skip tracking.

These integration tests use the ``mass`` fixture from ``tests/conftest.py``
which creates a full MusicAssistant instance with a real SQLite database in
a temporary directory.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from music_assistant_models.enums import MediaType
from music_assistant_models.media_items import Artist, ProviderMapping, Track
from music_assistant_models.unique_list import UniqueList

from music_assistant.constants import DB_TABLE_PLAY_EVENTS
from music_assistant.mass import MusicAssistant


def _library_mapping() -> set[ProviderMapping]:
    """Create a single library provider mapping with a unique provider item id."""
    return {
        ProviderMapping(
            item_id=uuid4().hex,
            provider_domain="library",
            provider_instance="library",
            in_library=True,
        )
    }


async def _add_track(mass: MusicAssistant, name: str) -> Track:
    """Add a minimal track to the library and return the (re-fetched) stored item."""
    artist = await mass.music.artists.add_item_to_library(
        Artist(
            item_id="0",
            provider="library",
            name=f"{name} Artist",
            provider_mappings=_library_mapping(),
        )
    )
    added = await mass.music.tracks.add_item_to_library(
        Track(
            item_id="0",
            provider="library",
            name=name,
            duration=180,
            provider_mappings=_library_mapping(),
            artists=UniqueList([artist]),
        )
    )
    return await mass.music.tracks.get_library_item(added.item_id)


async def _events_for_item(
    mass: MusicAssistant,
    track: Track,
    userid: str,
) -> list[dict[str, Any]]:
    """Read all play_events rows for a given track and user."""
    rows: list[dict[str, Any]] = []
    async for row in mass.music.database.iter_items(
        DB_TABLE_PLAY_EVENTS,
        match={"item_id": track.item_id, "userid": userid},
    ):
        rows.append(dict(row))
    return rows


async def test_finished_event_is_recorded(mass: MusicAssistant) -> None:
    """mark_item_played with fully_played=True records a 'finished' event."""
    user = await mass.webserver.auth.create_user("finisher")
    track = await _add_track(mass, "FinisherTrack")

    await mass.music.mark_item_played(
        track, fully_played=True, seconds_played=180, userid=user.user_id
    )

    rows = await _events_for_item(mass, track, user.user_id)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "finished"
    assert rows[0]["seconds_played"] == 180
    assert rows[0]["fully_played"] is True


async def test_incomplete_play_does_not_record_finish_event(
    mass: MusicAssistant,
) -> None:
    """mark_item_played with fully_played=False does not record a finish event."""
    user = await mass.webserver.auth.create_user("skipper")
    track = await _add_track(mass, "SkipTrack")

    await mass.music.mark_item_played(
        track, fully_played=False, seconds_played=10, userid=user.user_id
    )

    rows = await _events_for_item(mass, track, user.user_id)
    # No 'finished' event should exist; only the music controller writes to
    # play_events on fully_played=True in mark_item_played().
    finished_rows = [r for r in rows if r["event_type"] == "finished"]
    assert len(finished_rows) == 0


async def test_multiple_finishes_create_multiple_events(
    mass: MusicAssistant,
) -> None:
    """Re-playing the same track records separate events each time."""
    user = await mass.webserver.auth.create_user("repeattrack")
    track = await _add_track(mass, "RepeatTrack")

    await mass.music.mark_item_played(
        track, fully_played=True, seconds_played=180, userid=user.user_id
    )
    await mass.music.mark_item_played(
        track, fully_played=True, seconds_played=180, userid=user.user_id
    )
    await mass.music.mark_item_played(
        track, fully_played=True, seconds_played=180, userid=user.user_id
    )

    rows = await _events_for_item(mass, track, user.user_id)
    assert len(rows) == 3
    assert all(r["event_type"] == "finished" for r in rows)


async def test_different_users_get_separate_events(
    mass: MusicAssistant,
) -> None:
    """Events are tracked per-user, not globally."""
    user_a = await mass.webserver.auth.create_user("userA")
    user_b = await mass.webserver.auth.create_user("userB")
    track = await _add_track(mass, "CrossUserTrack")

    await mass.music.mark_item_played(
        track, fully_played=True, userid=user_a.user_id
    )
    await mass.music.mark_item_played(
        track, fully_played=True, userid=user_b.user_id
    )

    rows_a = await _events_for_item(mass, track, user_a.user_id)
    rows_b = await _events_for_item(mass, track, user_b.user_id)
    assert len(rows_a) == 1
    assert len(rows_b) == 1
    assert rows_a[0]["userid"] == user_a.user_id
    assert rows_b[0]["userid"] == user_b.user_id


async def test_event_row_contains_queue_id(mass: MusicAssistant) -> None:
    """The event row carries the queue_id from the mark_item_played call."""
    user = await mass.webserver.auth.create_user("queueidtest")
    track = await _add_track(mass, "QueueIdTrack")

    await mass.music.mark_item_played(
        track,
        fully_played=True,
        userid=user.user_id,
        queue_id="my_test_queue_123",
    )

    rows = await _events_for_item(mass, track, user.user_id)
    assert len(rows) == 1
    assert rows[0]["queue_id"] == "my_test_queue_123"


async def test_event_row_contains_media_type(mass: MusicAssistant) -> None:
    """The event row preserves the media_type of the played item."""
    user = await mass.webserver.auth.create_user("mediatype")
    track = await _add_track(mass, "MediaTypeTrack")

    await mass.music.mark_item_played(
        track, fully_played=True, userid=user.user_id
    )

    rows = await _events_for_item(mass, track, user.user_id)
    assert len(rows) == 1
    assert rows[0]["media_type"] == MediaType.TRACK.value
