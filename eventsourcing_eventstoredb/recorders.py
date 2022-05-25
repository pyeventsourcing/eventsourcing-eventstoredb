# -*- coding: utf-8 -*-
import json
import re
import sys
from typing import Any, List, Optional, Sequence
from uuid import UUID

from esdbclient import ESDB_EVENTS_REGEX, EsdbClient, NewEvent
from esdbclient.exceptions import ExpectedPositionError, StreamNotFound
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    IntegrityError,
    Notification,
    PersistenceError,
    ProgrammingError,
    StoredEvent,
)


class EventStoreDBAggregateRecorder(AggregateRecorder):
    SNAPSHOT_STREAM_PREFIX = "snapshot-$"

    def __init__(
        self,
        client: EsdbClient,
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
        originator_ids = list(set([e.originator_id for e in stored_events]))
        if len(originator_ids) == 0:
            return []
        elif len(originator_ids) > 1:
            raise ProgrammingError(
                "EventStoreDB can't atomically store events in more than one stream"
            )
        else:
            stream_name = str(originator_ids[0])

        first_originator_version = stored_events[0].originator_version
        if first_originator_version == 0:
            expected_position = None
        else:
            expected_position = first_originator_version - 1
        new_events: List[NewEvent] = []
        for i, stored_event in enumerate(stored_events):
            if stored_event.originator_version != i + first_originator_version:
                raise IntegrityError("Originator version out of sequence")

        # Protect against appending old snapshot after new.
        if self.for_snapshotting:
            recorded_snapshots = list(
                self.select_events(
                    originator_id=originator_ids[0],
                    desc=True,
                    limit=1,
                )
            )
            if len(recorded_snapshots) > 0:
                last_snapshot = recorded_snapshots[0]
                if last_snapshot.originator_version > first_originator_version:
                    return []

        # Convert StoredEvent objects to NewEvent objects.
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
            )
            new_events.append(new_event)
        try:
            if self.for_snapshotting:
                stream_name = self.create_snapshot_stream_name(stream_name)
                expected_position = -1  # Disable OCC.
            commit_position = self.client.append_events(
                stream_name=stream_name,
                expected_position=expected_position,
                events=new_events,
            )
        except ExpectedPositionError as e:
            raise IntegrityError(e) from e
        except Exception as e:
            raise PersistenceError(e) from e
        return [commit_position] * len(new_events)  # The best we can do?

    def create_snapshot_stream_name(self, stream_name: str) -> str:
        # return str(uuid5(NAMESPACE_OID, f"/snapshots/{stream_name}"))
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
                position = lte
                if gt is not None:
                    _limit = max(0, lte - gt)
                    if limit is None:
                        limit = _limit
                    else:
                        limit = min(limit, _limit)
            else:
                position = None
                if gt is not None:
                    current_position = self.client.get_stream_position(stream_name)
                    if current_position is None:
                        return []
                    _limit = max(0, current_position - gt)
                    if limit is None:
                        limit = _limit
                    else:
                        limit = min(limit, _limit)

        recorded_events = self.client.read_stream_events(
            stream_name=stream_name,
            position=position,
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
        except StreamNotFound:
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
        start: int,
        limit: int,
        stop: Optional[int] = None,
        topics: Sequence[str] = (),
    ) -> List[Notification]:

        # Assume reading from +1 the last commit position, so
        # subtract 1, and then drop the first event.
        if start > 0:
            start_commit_position = start - 1
            if limit is not None:
                limit += 1
        else:
            start_commit_position = None

        recorded_events = self.client.read_all_events(
            position=start_commit_position,
            filter_exclude=(ESDB_EVENTS_REGEX, ".*Snapshot"),
            filter_include=[re.escape(t) for t in topics] or [],
            limit=limit,
        )

        notifications = []
        drop_first = start is not None
        for recorded_event in recorded_events:
            # Drop the first, but only if 'start' is its 'commit position'.
            if drop_first:
                drop_first = False
                if recorded_event.commit_position == start_commit_position:
                    continue

            # Catch a failure to reconstruct UUID, so we can see what didn't work.
            try:
                originator_id = UUID(recorded_event.stream_name)
            except ValueError as e:
                raise ValueError(f"{e}: {recorded_event.stream_name}") from e

            # Construct a Notification object from the RecordedEvent object.
            notification = Notification(
                id=recorded_event.commit_position,
                originator_id=originator_id,
                originator_version=recorded_event.stream_position,
                topic=recorded_event.type,
                state=recorded_event.data,
            )
            notifications.append(notification)

            # Check we aren't going over the limit, in case we didn't drop the first.
            if len(notifications) == limit:
                break

            # Stop if we reached the 'stop' position.
            if stop is not None and recorded_event.commit_position >= stop:
                break

        return notifications

    def max_notification_id(self) -> int:
        return self.client.get_commit_position(
            filter_exclude=(ESDB_EVENTS_REGEX, ".*Snapshot"),
        )
