# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import sys
from typing import Any, List, Optional, Sequence, Union
from uuid import UUID

import esdbclient.exceptions
from esdbclient import (
    DEFAULT_EXCLUDE_FILTER,
    EventStoreDBClient,
    NewEvent,
    RecordedEvent,
    StreamState,
)
from esdbclient.exceptions import NotFound, WrongCurrentVersion
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


class EventStoreDBAggregateRecorder(AggregateRecorder):
    SNAPSHOT_STREAM_PREFIX = "snapshot-$"

    def __init__(
        self,
        client: EventStoreDBClient,
        for_snapshotting: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super(EventStoreDBAggregateRecorder, self).__init__(*args, **kwargs)
        self.client = client
        self.for_snapshotting = for_snapshotting

    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        self._insert_events(stored_events, **kwargs)
        return None

    def _insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
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
            originator_ids = list(set([e.originator_id for e in stored_events]))
            if len(originator_ids) == 0:
                return []
            elif len(originator_ids) > 1:
                raise ProgrammingError(
                    "EventStoreDB can't atomically store events in more than one stream"
                )

            # Make sure stored events have a gapless sequence of originator_versions.
            for i in range(1, len(stored_events)):
                if (
                    stored_events[i].originator_version
                    != i + stored_events[0].originator_version
                ):
                    raise IntegrityError("Gap detected in originator versions")

        # Convert StoredEvent objects to NewEvent objects.
        new_events: List[NewEvent] = []
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
            current_version: Union[int, StreamState] = StreamState.ANY  # Disable OCC.
        else:
            if stored_events[0].originator_version == 0:
                current_version = StreamState.NO_STREAM
            else:
                current_version = stored_events[0].originator_version - 1

        try:
            commit_position = self.client.append_events(
                stream_name=stream_name,
                current_version=current_version,
                events=new_events,
            )
        except WrongCurrentVersion as e:
            raise IntegrityError(e) from e
        except Exception as e:
            raise PersistenceError(e) from e
        return [commit_position] * len(new_events)  # The best we can do?

    def create_snapshot_stream_name(self, stream_name: str) -> str:
        return self.SNAPSHOT_STREAM_PREFIX + stream_name

    def select_events(  # noqa: C901
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
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
                    if limit is None:
                        limit = _limit
                    else:
                        limit = min(limit, _limit)
            else:
                position = None
                if lte is not None:
                    _limit = max(0, lte + 1)
                    if limit is None:
                        limit = _limit
                    else:
                        limit = min(limit, _limit)

        else:
            if lte is not None:
                current_position = self.client.get_current_version(stream_name)
                if current_position is StreamState.NO_STREAM:
                    return []
                position = lte = min(current_position, lte)
                if gt is not None:
                    _limit = max(0, lte - gt)
                    if limit is None:
                        limit = _limit
                    else:
                        limit = min(limit, _limit)
            else:
                position = None
                if gt is not None:
                    current_position = self.client.get_current_version(stream_name)
                    if current_position is StreamState.NO_STREAM:
                        return []
                    _limit = max(0, current_position - gt)
                    if limit is None:
                        limit = _limit
                    else:
                        limit = min(limit, _limit)

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
        except NotFound:
            return []

        return stored_events


class EventStoreDBApplicationRecorder(
    EventStoreDBAggregateRecorder, ApplicationRecorder
):
    def insert_events(
        self, stored_events: List[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        return self._insert_events(stored_events, **kwargs)

    def select_notifications(
        self,
        start: int | None,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
        inclusive_of_start: bool = True,
    ) -> List[Notification]:
        if not inclusive_of_start:
            limit += 1
        recorded_events = self.client.read_all(
            commit_position=start,
            filter_exclude=DEFAULT_EXCLUDE_FILTER + (".*Snapshot",),
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
            notification = self._construct_notification(recorded_event)
            notifications.append(notification)

            # Check we aren't going over the limit, in case we didn't drop the first.
            if len(notifications) == limit:
                break

            # Stop if we reached the 'stop' position.
            assert isinstance(recorded_event.commit_position, int)
            if stop is not None and recorded_event.commit_position >= stop:
                break

        return notifications

    def _construct_notification(self, recorded_event: RecordedEvent) -> Notification:
        # Catch a failure to reconstruct UUID, so we can see what didn't work.
        try:
            originator_id = UUID(recorded_event.stream_name)
        except ValueError as e:
            raise ValueError(f"{e}: {recorded_event.stream_name}") from e

        assert recorded_event.commit_position is not None
        notification = Notification(
            id=recorded_event.commit_position,
            originator_id=originator_id,
            originator_version=recorded_event.stream_position,
            topic=recorded_event.type,
            state=recorded_event.data,
        )
        return notification

    def max_notification_id(self) -> int | None:
        return self.client.get_commit_position(
            filter_exclude=(*DEFAULT_EXCLUDE_FILTER, ".*Snapshot"),
        )

    def subscribe(self, gt: int | None = None) -> Subscription[ApplicationRecorder]:
        return EventStoreDBSubscription(self, gt)


class EventStoreDBSubscription(Subscription[EventStoreDBApplicationRecorder]):
    def __init__(
        self, recorder: EventStoreDBApplicationRecorder, gt: int | None = None
    ):
        super(EventStoreDBSubscription, self).__init__(recorder=recorder, gt=gt)
        self._esdb_subscription = self._recorder.client.subscribe_to_all(
            commit_position=self._last_notification_id
        )

    def __next__(self) -> Notification:
        while not self._has_been_stopped:
            try:
                recorded_event = next(self._esdb_subscription)
            except esdbclient.exceptions.ConsumerTooSlow:
                # Sometimes the database drops the connection just after starting.
                self._esdb_subscription = self._recorder.client.subscribe_to_all(
                    commit_position=self._last_notification_id
                )
            else:
                notification = self._recorder._construct_notification(recorded_event)
                self._last_notification_id = notification.id
                return notification

        raise StopIteration

    def stop(self) -> None:
        super().stop()
        self._esdb_subscription.stop()
