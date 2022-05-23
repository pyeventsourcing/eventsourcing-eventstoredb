# -*- coding: utf-8 -*-
import sys
from typing import Any, List, Optional, Sequence
from uuid import UUID

from esdbclient.client import (
    EsdbClient,
    ExpectedPositionError,
    NewEvent,
    StreamNotFound,
)
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
        # Todo: Need to get the IDs in the response. But only get an AppendResp msg.
        for stored_event in stored_events:
            new_event = NewEvent(
                type=stored_event.topic,
                data=stored_event.state,
                metadata=b"",
            )
            new_events.append(new_event)
        try:
            if self.for_snapshotting:
                raise NotImplementedError("Snapshots not implemented yet")
            else:
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

    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        if self.for_snapshotting:
            return []
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

        recorded_events = self.client.read_stream_events(
            stream_name=str(originator_id),
            position=position,
            backwards=desc,
            limit=limit if limit is not None else sys.maxsize,
        )

        stored_events = []
        try:
            for ev in recorded_events:
                se = StoredEvent(
                    originator_id=originator_id,
                    originator_version=ev.stream_position,
                    topic=ev.type,
                    state=ev.data,
                )
                stored_events.append(se)
        except StreamNotFound:
            return []

        return stored_events

    def max_notification_id(self) -> int:
        recorded_events = self.client.read_all_events(
            backwards=True,
            limit=1,
        )
        for ev in recorded_events:
            # Todo: Check this is > 0, if not then add 1 to everything.
            assert ev.commit_position > 0, "First commit position is zero.."
            return ev.commit_position
        else:
            return 0


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

        recorded_events = self.client.read_all_events(
            position=start if start > 0 else None,
            limit=limit,
        )

        notifications = []
        for ev in recorded_events:
            if ev.stream_name.startswith("$$$"):
                # Todo: What actually is "$$$scavenges"? and why is it here?
                continue
            try:
                originator_id = UUID(ev.stream_name)
            except ValueError as e:
                raise ValueError(f"{e}: {ev.stream_name}") from e
            notification = Notification(
                id=ev.commit_position,
                originator_id=originator_id,
                originator_version=ev.stream_position,
                topic=ev.type,
                state=ev.data,
            )
            notifications.append(notification)
        return notifications
