# -*- coding: utf-8 -*-
from unittest import skip
from uuid import uuid4

from esdbclient.client import EsdbClient
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    StoredEvent,
)
from eventsourcing.tests.persistence import (
    AggregateRecorderTestCase,
    ApplicationRecorderTestCase,
)

from eventsourcing_eventstoredb.recorders import (
    EventStoreDBAggregateRecorder,
    EventStoreDBApplicationRecorder,
)
from tests.common import INSECURE_CONNECTION_STRING


class TestEventStoreDBAggregateRecorder(AggregateRecorderTestCase):
    INITIAL_VERSION = 0

    def setUp(self) -> None:
        self.client = EsdbClient(INSECURE_CONNECTION_STRING)

    def create_recorder(self) -> AggregateRecorder:
        return EventStoreDBAggregateRecorder(client=self.client)

    def test_insert_and_select(self) -> None:
        super(TestEventStoreDBAggregateRecorder, self).test_insert_and_select()


class TestEventStoreDBApplicationRecorder(ApplicationRecorderTestCase):
    INITIAL_VERSION = 0

    def setUp(self) -> None:
        # self.original_initial_version = Aggregate.INITIAL_VERSION
        # Aggregate.INITIAL_VERSION = 0
        self.client = EsdbClient(INSECURE_CONNECTION_STRING)

    def tearDown(self) -> None:
        del self.client
        # Aggregate.INITIAL_VERSION = self.original_initial_version

    def create_recorder(self) -> ApplicationRecorder:
        return EventStoreDBApplicationRecorder(client=self.client)

    @skip("Can't do notification ID arithmetic with EventStoreDB?")
    def test_insert_select(self) -> None:
        super().test_insert_select()

    def test_insert_select_easy_alternative_for_esdb(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        initial_max_notification_id = recorder.max_notification_id()

        # Check notifications methods work when there aren't any.
        self.assertEqual(
            recorder.max_notification_id(),
            initial_max_notification_id,
        )
        self.assertEqual(
            len(recorder.select_notifications(initial_max_notification_id, 3)),
            1,
        )

        # Write two stored events.
        originator_id1 = uuid4()
        originator_id2 = uuid4()

        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION,
            topic="topic1",
            state=b"state1",
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 1,
            topic="topic2",
            state=b"state2",
        )
        stored_event3 = StoredEvent(
            originator_id=originator_id2,
            originator_version=self.INITIAL_VERSION,
            topic="topic3",
            state=b"state3",
        )

        notification_ids = recorder.insert_events([])
        self.assertEqual(notification_ids, [])

        notification_ids1 = recorder.insert_events([stored_event1, stored_event2])
        assert notification_ids1
        max_notification_id1 = notification_ids1[-1]
        self.assertGreater(max_notification_id1, initial_max_notification_id)

        notification_ids2 = recorder.insert_events([stored_event3])
        assert notification_ids2
        max_notification_id2 = notification_ids2[-1]
        self.assertGreater(max_notification_id2, max_notification_id1)

        stored_events1 = recorder.select_events(originator_id1)
        stored_events2 = recorder.select_events(originator_id2)

        # Check we got what was written.
        self.assertEqual(len(stored_events1), 2)
        self.assertEqual(len(stored_events2), 1)

        notifications = recorder.select_notifications(initial_max_notification_id, 4)[
            1:
        ]
        self.assertEqual(len(notifications), 3)
        # self.assertEqual(notifications[0].id, initial_max_notification_id + 1)
        self.assertGreater(notifications[0].id, initial_max_notification_id)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].id, max_notification_id1)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")
        self.assertEqual(notifications[2].id, max_notification_id2)
        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b"state3")

    def test_concurrent_no_conflicts(self) -> None:
        super().test_concurrent_no_conflicts()


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
