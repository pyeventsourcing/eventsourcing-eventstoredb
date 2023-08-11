# -*- coding: utf-8 -*-
from uuid import uuid4

from esdbclient import EventStoreDBClient
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
        self.client = EventStoreDBClient(INSECURE_CONNECTION_STRING)

    def create_recorder(self) -> AggregateRecorder:
        return EventStoreDBAggregateRecorder(client=self.client)

    def test_insert_and_select(self) -> None:
        super(TestEventStoreDBAggregateRecorder, self).test_insert_and_select()


class TestEventStoreDBApplicationRecorder(ApplicationRecorderTestCase):
    INITIAL_VERSION = 0

    def setUp(self) -> None:
        # self.original_initial_version = Aggregate.INITIAL_VERSION
        # Aggregate.INITIAL_VERSION = 0
        self.client = EventStoreDBClient(INSECURE_CONNECTION_STRING)

    def tearDown(self) -> None:
        del self.client
        # Aggregate.INITIAL_VERSION = self.original_initial_version

    def create_recorder(self) -> ApplicationRecorder:
        return EventStoreDBApplicationRecorder(client=self.client)

    def test_insert_select(self) -> None:
        # super().test_insert_select()

        # Construct the recorder.
        recorder = self.create_recorder()

        # Get the current max notification ID.
        max_notification_id1 = recorder.max_notification_id()

        # Check notifications methods work when there aren't any.
        self.assertEqual(
            recorder.max_notification_id(),
            max_notification_id1,
        )
        self.assertEqual(
            len(recorder.select_notifications(max_notification_id1 + 1, 10)),
            0,
        )
        self.assertEqual(
            len(
                recorder.select_notifications(
                    max_notification_id1 + 1, 3, topics=["topic1"]
                )
            ),
            0,
        )

        # Check inserting an empty list gives an empty list of notification IDs.
        notification_ids = recorder.insert_events([])
        self.assertEqual(notification_ids, [])

        # Define three stored events with two different originator IDs.
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

        # Insert two events.
        notification_ids = recorder.insert_events([stored_event1, stored_event2])

        # Check we got two event notification IDs.
        assert notification_ids is not None
        self.assertEqual(len(notification_ids), 2)

        # Check they are larger than the initial max notification ID.
        self.assertGreater(notification_ids[0], max_notification_id1)
        self.assertGreater(notification_ids[1], max_notification_id1)

        # Check the last one is the same as the current max notification ID.
        max_notification_id2 = recorder.max_notification_id()
        self.assertEqual(notification_ids[-1], max_notification_id2)

        # Insert the third event.
        notification_ids = recorder.insert_events([stored_event3])

        # Check we got one event notification ID.
        assert notification_ids is not None
        self.assertEqual(len(notification_ids), 1)

        # Check they are larger than the last max notification ID.
        self.assertGreater(notification_ids[0], max_notification_id2)

        # Check the last one is the same as the current max notification ID.
        max_notification_id3 = recorder.max_notification_id()
        self.assertEqual(notification_ids[-1], max_notification_id3)

        # Select the recorded events for each originator ID.
        stored_events1 = recorder.select_events(originator_id1)
        stored_events2 = recorder.select_events(originator_id2)

        # Check we got what was written.
        self.assertEqual(len(stored_events1), 2)
        self.assertEqual(stored_events1[0].originator_id, originator_id1)
        self.assertEqual(stored_events1[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(stored_events1[1].originator_id, originator_id1)
        self.assertEqual(stored_events1[1].originator_version, self.INITIAL_VERSION + 1)
        self.assertEqual(len(stored_events2), 1)
        self.assertEqual(stored_events2[0].originator_id, originator_id2)
        self.assertEqual(stored_events2[0].originator_version, self.INITIAL_VERSION)

        # Select notifications from initial max notification ID.
        notifications = recorder.select_notifications(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b"state1")
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION + 1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b"state2")
        self.assertEqual(notifications[1].id, max_notification_id2)

        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b"state3")
        self.assertEqual(notifications[2].id, max_notification_id3)

        # Select notification by topic (all topics).
        notifications = recorder.select_notifications(
            max_notification_id1 + 1, 10, topics=["topic1", "topic2", "topic3"]
        )

        # Check we got three notifications.
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION + 1)
        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].originator_version, self.INITIAL_VERSION)

        # Select notification by topic (topic1 only).
        notifications = recorder.select_notifications(
            max_notification_id1 + 1, 10, topics=["topic1"]
        )

        # Check we got the correct notification.
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select notification by topic (topic2 only).
        notifications = recorder.select_notifications(
            max_notification_id1 + 1, 10, topics=["topic2"]
        )

        # Check we got the correct notification.
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION + 1)

        # Select notification by topic (topic3 only).
        notifications = recorder.select_notifications(
            max_notification_id1 + 1, 10, topics=["topic3"]
        )

        # Check we got the correct notification.
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id2)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select notification by topic (topic1 and topic3 only).
        notifications = recorder.select_notifications(
            max_notification_id1 + 1, 10, topics=["topic1", "topic3"]
        )

        # Check we got the correct notifications.
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[1].originator_id, originator_id2)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION)

        # Select a limited number of notifications from initial position.
        notifications = recorder.select_notifications(max_notification_id1 + 1, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select a limited number of notifications from later position.
        notifications = recorder.select_notifications(max_notification_id2 + 1, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id2)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select notifications between two positions
        notifications = recorder.select_notifications(
            start=max_notification_id1 + 1, limit=10, stop=max_notification_id2
        )
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION + 1)

    def test_concurrent_no_conflicts(self) -> None:
        super().test_concurrent_no_conflicts()


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
