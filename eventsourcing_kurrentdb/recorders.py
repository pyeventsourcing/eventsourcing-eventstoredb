from __future__ import annotations

import json
import re
import sys
from typing import TYPE_CHECKING, Any
from uuid import UUID

import kurrentdbclient.exceptions
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    IntegrityError,
    Notification,
    PersistenceError,
    ProgrammingError,
    StoredEvent,
    Subscription,
)
from kurrentdbclient import (
    DEFAULT_EXCLUDE_FILTER,
    KurrentDBClient,
    NewEvent,
    RecordedEvent,
    StreamState,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class KurrentDBAggregateRecorder(AggregateRecorder):
    SNAPSHOT_STREAM_PREFIX = "snapshot-$"

    def __init__(
        self,
        client: KurrentDBClient,
        *args: Any,
        for_snapshotting: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.client = client
        self.for_snapshotting = for_snapshotting

    def insert_events(
        self, stored_events: list[StoredEvent], **kwargs: Any
    ) -> Sequence[int] | None:
        self._insert_events(stored_events, **kwargs)
        return None

    def _insert_events(  # noqa: C901
        self, stored_events: list[StoredEvent], **kwargs: Any
    ) -> Sequence[int] | None:
        if self.for_snapshotting:
            # Protect against appending old snapshot after new.
            assert len(stored_events) == 1, len(stored_events)
            recorded_snapshots = list(
                self.select_events(
                    originator_id=stored_events[0].originator_id,
                    desc=True,
                    limit=1,
                )
            )
            if (
                len(recorded_snapshots) > 0
                and recorded_snapshots[0].originator_version
                > stored_events[0].originator_version
            ):
                return []
        else:
            # Make sure all stored events have same originator ID.
            set_of_originator_ids = {e.originator_id for e in stored_events}
            if len(set_of_originator_ids) == 0:
                return []
            if len(set_of_originator_ids) > 1:
                msg = "KurrentDB can't atomically store events in more than one stream"
                raise ProgrammingError(msg)

            # Make sure stored events have a gapless sequence of originator_versions.
            for i in range(1, len(stored_events)):
                if (
                    stored_events[i].originator_version
                    != i + stored_events[0].originator_version
                ):
                    msg = "Gap detected in originator versions"
                    raise IntegrityError(msg)

        # Convert StoredEvent objects to NewEvent objects.
        new_events: list[NewEvent] = []
        for stored_event in stored_events:
            if self.for_snapshotting:
                metadata = json.dumps(
                    {"originator_version": stored_event.originator_version}
                ).encode("utf8")
            else:
                metadata = b""
            new_event = NewEvent(
                type=stored_event.topic,
                data=stored_event.state,
                metadata=metadata,
                content_type="application/octet-stream",
            )
            new_events.append(new_event)

        # Decide 'stream_name' argument.
        stream_name = str(stored_events[0].originator_id)
        if self.for_snapshotting:
            stream_name = self.create_snapshot_stream_name(stream_name)

        # Decide 'current_version' argument.
        if self.for_snapshotting:
            current_version: int | StreamState = StreamState.ANY  # Disable OCC.
        elif stored_events[0].originator_version == 0:
            current_version = StreamState.NO_STREAM
        else:
            current_version = stored_events[0].originator_version - 1

        try:
            commit_position = self.client.append_events(
                stream_name=stream_name,
                current_version=current_version,
                events=new_events,
            )
        except kurrentdbclient.exceptions.WrongCurrentVersionError as e:
            raise IntegrityError(e) from e
        except Exception as e:
            raise PersistenceError(e) from e
        return [commit_position] * len(new_events)  # The best we can do?

    def create_snapshot_stream_name(self, stream_name: str) -> str:
        return self.SNAPSHOT_STREAM_PREFIX + stream_name

    def select_events(  # noqa: C901
        self,
        originator_id: UUID,
        *,
        gt: int | None = None,
        lte: int | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> list[StoredEvent]:
        stream_name = str(originator_id)
        if self.for_snapshotting:
            if desc and lte:
                return []
            stream_name = self.create_snapshot_stream_name(stream_name)

        if not desc:
            if gt is not None:
                position = gt + 1
                if lte is not None:
                    _limit = max(0, lte - gt)
                    limit = _limit if limit is None else min(limit, _limit)
            else:
                position = None
                if lte is not None:
                    _limit = max(0, lte + 1)
                    limit = _limit if limit is None else min(limit, _limit)

        elif lte is not None:
            current_position = self.client.get_current_version(stream_name)
            if current_position is StreamState.NO_STREAM:
                return []
            position = lte = min(current_position, lte)
            if gt is not None:
                _limit = max(0, lte - gt)
                limit = _limit if limit is None else min(limit, _limit)
        else:
            position = None
            if gt is not None:
                current_position = self.client.get_current_version(stream_name)
                if current_position is StreamState.NO_STREAM:
                    return []
                _limit = max(0, current_position - gt)
                limit = _limit if limit is None else min(limit, _limit)

        if limit == 0:
            return []
        recorded_events = self.client.read_stream(
            stream_name=stream_name,
            stream_position=position,
            backwards=desc,
            limit=limit if limit is not None else sys.maxsize,
        )

        stored_events = []
        try:
            for ev in recorded_events:
                if self.for_snapshotting:
                    originator_version = json.loads(ev.metadata.decode("utf8"))[
                        "originator_version"
                    ]
                else:
                    originator_version = ev.stream_position

                se = StoredEvent(
                    originator_id=originator_id,
                    originator_version=originator_version,
                    topic=ev.type,
                    state=ev.data,
                )
                stored_events.append(se)
        except kurrentdbclient.exceptions.NotFoundError:
            return []

        return stored_events


def _construct_notification(recorded_event: RecordedEvent) -> Notification:
    # Catch a failure to reconstruct UUID, so we can see what didn't work.
    try:
        originator_id = UUID(recorded_event.stream_name)
    except ValueError as e:
        msg = f"{e}: {recorded_event.stream_name}"
        raise ValueError(msg) from e

    assert recorded_event.commit_position is not None
    return Notification(
        id=recorded_event.commit_position,
        originator_id=originator_id,
        originator_version=recorded_event.stream_position,
        topic=recorded_event.type,
        state=recorded_event.data,
    )


class KurrentDBApplicationRecorder(KurrentDBAggregateRecorder, ApplicationRecorder):
    def insert_events(
        self, stored_events: list[StoredEvent], **kwargs: Any
    ) -> Sequence[int] | None:
        return self._insert_events(stored_events, **kwargs)

    def select_notifications(
        self,
        start: int | None,
        limit: int,
        stop: int | None = None,
        topics: Sequence[str] = (),
        *,
        inclusive_of_start: bool = True,
    ) -> list[Notification]:
        original_limit = limit
        if not inclusive_of_start:
            limit += 1
        recorded_events = self.client.read_all(
            commit_position=start,
            filter_exclude=(*DEFAULT_EXCLUDE_FILTER, ".*Snapshot"),
            filter_include=[re.escape(t) for t in topics] or [],
            limit=limit,
        )

        notifications = []
        for recorded_event in recorded_events:
            # Maybe drop first event.
            if (
                not inclusive_of_start
                and isinstance(start, int)
                and recorded_event.commit_position == start
            ):
                continue

            # Construct a Notification object from the RecordedEvent object.
            assert isinstance(recorded_event.commit_position, int)
            notification = _construct_notification(recorded_event)
            notifications.append(notification)

            # Check we aren't going over the limit, in case we didn't drop the first.
            if len(notifications) == original_limit:
                break

            # Stop if we reached the 'stop' position.
            assert isinstance(recorded_event.commit_position, int)
            if stop is not None and recorded_event.commit_position >= stop:
                break

        return notifications

    def max_notification_id(self) -> int | None:
        return self.client.get_commit_position(
            filter_exclude=(*DEFAULT_EXCLUDE_FILTER, ".*Snapshot"),
        )

    def subscribe(
        self, gt: int | None = None, topics: Sequence[str] = ()
    ) -> Subscription[ApplicationRecorder]:
        return KurrentDBSubscription(recorder=self, gt=gt, topics=topics)


class KurrentDBSubscription(Subscription[KurrentDBApplicationRecorder]):
    def __init__(
        self,
        recorder: KurrentDBApplicationRecorder,
        gt: int | None = None,
        topics: Sequence[str] = (),
    ):
        super().__init__(recorder=recorder, gt=gt, topics=topics)
        self._esdb_subscription = self._recorder.client.subscribe_to_all(
            commit_position=self._last_notification_id,
            filter_exclude=(*DEFAULT_EXCLUDE_FILTER, ".*Snapshot"),
            filter_include=self._topics,  # has priority
        )

    def __next__(self) -> Notification:
        while not self._has_been_stopped:
            notification = self._next_notification()
            if notification is None:  # pragma: no cover
                continue
            return notification

        raise StopIteration

    def _next_notification(self) -> Notification | None:
        try:
            recorded_event = next(self._esdb_subscription)
        except kurrentdbclient.exceptions.ConsumerTooSlowError:  # pragma: no cover
            # Sometimes the database drops the connection just after starting.
            self._esdb_subscription = self._recorder.client.subscribe_to_all(
                commit_position=self._last_notification_id,
                filter_exclude=(*DEFAULT_EXCLUDE_FILTER, ".*Snapshot"),
                filter_include=self._topics,  # has priority
            )
            return None
        else:
            notification = _construct_notification(recorded_event)
            self._last_notification_id = notification.id
            return notification

    def stop(self) -> None:
        super().stop()
        self._esdb_subscription.stop()
