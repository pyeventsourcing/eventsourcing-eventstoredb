from __future__ import annotations

from concurrent.futures.thread import ThreadPoolExecutor
from typing import cast
from uuid import uuid4

import kurrentdbclient.exceptions
from eventsourcing.domain import datetime_now_with_tzinfo
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    PersistenceError,
    ProgrammingError,
    StoredEvent,
)
from eventsourcing.tests.persistence import (
    AggregateRecorderTestCase,
    ApplicationRecorderTestCase,
)
from kurrentdbclient import KurrentDBClient, NewEvent, StreamState

from eventsourcing_kurrentdb.recorders import (
    KurrentDBAggregateRecorder,
    KurrentDBApplicationRecorder,
)
from tests.common import INSECURE_CONNECTION_STRING


class TestKurrentDBAggregateRecorder(AggregateRecorderTestCase):
    INITIAL_VERSION = 0

    def setUp(self) -> None:
        self.client = KurrentDBClient(INSECURE_CONNECTION_STRING)

    def create_recorder(self) -> AggregateRecorder:
        return KurrentDBAggregateRecorder(client=self.client)

    def test_insert_and_select(self) -> None:
        super().test_insert_and_select()
        # Construct the recorder.
        recorder = self.create_recorder()

        # Write three stored events.
        originator_id1 = uuid4()
        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION,
            topic="topic1",
            state=b'{"state": "state1"}',
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 1,
            topic="topic2",
            state=b'{"state": "state2"}',
        )
        stored_event3 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 2,
            topic="topic3",
            state=b'{"state": "state3"}',
        )

        # Insert three events.
        recorder.insert_events([stored_event1, stored_event2, stored_event3])

        # Select events with gt, lte and limit args.
        self.assertEqual(  # reads from after start, limited by limit
            recorder.select_events(originator_id1, gt=0, lte=30, limit=0),
            [],
        )
        self.assertEqual(  # reads from after start, limited by limit
            recorder.select_events(originator_id1, gt=0, lte=30, limit=1),
            [stored_event2],
        )
        self.assertEqual(  # reads from after start, limited by limit
            recorder.select_events(originator_id1, gt=0, lte=30, limit=2),
            [stored_event2, stored_event3],
        )
        self.assertEqual(  # reads from after start, limited by lte
            recorder.select_events(originator_id1, gt=0, lte=0, limit=10),
            [],
        )
        self.assertEqual(  # reads from after start, limited by lte
            recorder.select_events(originator_id1, gt=0, lte=1, limit=10),
            [stored_event2],
        )
        self.assertEqual(  # reads from after start, limited by lte
            recorder.select_events(originator_id1, gt=0, lte=2, limit=10),
            [stored_event2, stored_event3],
        )
        self.assertEqual(  # reads from after start, limited by lte
            recorder.select_events(originator_id1, gt=1, lte=2, limit=10),
            [stored_event3],
        )
        self.assertEqual(  # reads from after start, limited by lte
            recorder.select_events(originator_id1, gt=2, lte=10, limit=10),
            [],
        )

        # Select events with lte and limit args.
        self.assertEqual(  # read limited by limit
            recorder.select_events(originator_id1, lte=10, limit=1),
            [stored_event1],
        )
        self.assertEqual(  # read limited by limit
            recorder.select_events(originator_id1, lte=10, limit=2),
            [stored_event1, stored_event2],
        )
        self.assertEqual(  # read limited by lte
            recorder.select_events(originator_id1, lte=0, limit=10),
            [stored_event1],
        )
        self.assertEqual(  # read limited by lte
            recorder.select_events(originator_id1, lte=1, limit=10),
            [stored_event1, stored_event2],
        )
        self.assertEqual(  # read limited by lte
            recorder.select_events(originator_id1, lte=10, limit=10),
            [stored_event1, stored_event2, stored_event3],
        )
        self.assertEqual(  # read limited by both lte and limit
            recorder.select_events(originator_id1, lte=1, limit=1),
            [stored_event1],
        )

        # Select events with desc, gt, lte.
        self.assertEqual(  # reads from after end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=5, lte=10),
            [],
        )
        self.assertEqual(  # reads from after end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=2, lte=10),
            [],
        )
        self.assertEqual(  # reads from after end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=1, lte=10),
            [stored_event3],
        )
        self.assertEqual(  # reads from before end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=1, lte=1),
            [],
        )
        self.assertEqual(  # reads from before end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=0, lte=1),
            [stored_event2],
        )

        # Select events with desc, gt, lte and limit args.
        self.assertEqual(  # reads from after end, limited by given limit
            recorder.select_events(originator_id1, desc=True, gt=0, lte=3, limit=1),
            [stored_event3],
        )
        self.assertEqual(  # reads from end, limited by given limit
            recorder.select_events(originator_id1, desc=True, gt=0, lte=2, limit=1),
            [stored_event3],
        )
        self.assertEqual(  # reads from before end, limited by given limit
            recorder.select_events(originator_id1, desc=True, gt=0, lte=1, limit=1),
            [stored_event2],
        )

        self.assertEqual(  # reads from after end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=0, lte=3, limit=10),
            [stored_event3, stored_event2],
        )
        self.assertEqual(  # reads from end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=0, lte=2, limit=10),
            [stored_event3, stored_event2],
        )
        self.assertEqual(  # reads from before end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=0, lte=1, limit=10),
            [stored_event2],
        )

        self.assertEqual(  # reads from after end, limited by gt and limit
            recorder.select_events(originator_id1, desc=True, gt=0, lte=3, limit=2),
            [stored_event3, stored_event2],
        )
        self.assertEqual(  # reads from end, limited by gt and limit
            recorder.select_events(originator_id1, desc=True, gt=0, lte=2, limit=2),
            [stored_event3, stored_event2],
        )
        self.assertEqual(  # reads from before end, limited by gt and limit
            recorder.select_events(originator_id1, desc=True, gt=0, lte=1, limit=1),
            [stored_event2],
        )

        # Select events with desc, lte (NO STREAM).
        self.assertEqual(  # reads from after end, limited by limit
            recorder.select_events(uuid4(), desc=True, lte=10, limit=1),
            [],
        )

        # Select events with desc, lte and limit args.
        self.assertEqual(  # reads from after end, limited by limit
            recorder.select_events(originator_id1, desc=True, lte=10, limit=1),
            [stored_event3],
        )
        self.assertEqual(  # reads from end, limited by limit
            recorder.select_events(originator_id1, desc=True, lte=2, limit=1),
            [stored_event3],
        )
        self.assertEqual(  # reads from before end, limited by limit
            recorder.select_events(originator_id1, desc=True, lte=1, limit=1),
            [stored_event2],
        )
        self.assertEqual(  # reads from before end, limited by start of stream
            recorder.select_events(originator_id1, desc=True, lte=1, limit=10),
            [stored_event2, stored_event1],
        )

        # Select events with desc, gt
        self.assertEqual(  # reads until after end
            recorder.select_events(originator_id1, desc=True, gt=10),
            [],
        )
        self.assertEqual(  # reads until end
            recorder.select_events(originator_id1, desc=True, gt=1),
            [stored_event3],
        )
        self.assertEqual(  # reads until before end
            recorder.select_events(originator_id1, desc=True, gt=0),
            [stored_event3, stored_event2],
        )

        # Select events with desc, gt (NO STREAM)
        self.assertEqual(  # reads until before end
            recorder.select_events(uuid4(), desc=True, gt=1),
            [],
        )

        # Select events with desc, gt, limit
        self.assertEqual(  # reads until after end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=10, limit=10),
            [],
        )
        self.assertEqual(  # reads until end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=1, limit=10),
            [stored_event3],
        )
        self.assertEqual(  # reads until before end, limited by gt
            recorder.select_events(originator_id1, desc=True, gt=0, limit=10),
            [stored_event3, stored_event2],
        )
        self.assertEqual(  # reads until before end, limited by limit
            recorder.select_events(originator_id1, desc=True, gt=0, limit=1),
            [stored_event3],
        )
        self.assertEqual(  # reads until before end, limited by gt and limit
            recorder.select_events(originator_id1, desc=True, gt=1, limit=1),
            [stored_event3],
        )
        self.assertEqual(  # reads until before end, limited by limit
            recorder.select_events(originator_id1, desc=True, gt=0, limit=2),
            [stored_event3, stored_event2],
        )

        # Can't store events in more than one stream.
        stored_event4 = StoredEvent(
            originator_id=uuid4(),
            originator_version=self.INITIAL_VERSION,
            topic="topic4",
            state=b'{"state": "state4"}',
        )
        stored_event5 = StoredEvent(
            originator_id=uuid4(),
            originator_version=self.INITIAL_VERSION,
            topic="topic5",
            state=b'{"state": "state5"}',
        )
        with self.assertRaises(ProgrammingError):
            recorder.insert_events([stored_event4, stored_event5])


class TestKurrentDBApplicationRecorder(ApplicationRecorderTestCase):
    INITIAL_VERSION = 0
    EXPECT_CONTIGUOUS_NOTIFICATION_IDS = False

    def setUp(self) -> None:
        self.validate_uuids = False
        # self.original_initial_version = Aggregate.INITIAL_VERSION
        # Aggregate.INITIAL_VERSION = 0
        self.client = KurrentDBClient(INSECURE_CONNECTION_STRING)

    def tearDown(self) -> None:
        del self.client
        # Aggregate.INITIAL_VERSION = self.original_initial_version

    def create_recorder(self) -> ApplicationRecorder:
        recorder = KurrentDBApplicationRecorder(client=self.client)
        recorder.validate_uuids = self.validate_uuids
        return recorder

    def test_insert_select(self) -> None:
        # super().test_insert_select()

        # Construct the recorder.
        self.validate_uuids = True
        recorder = self.create_recorder()

        # Get the current max notification ID.
        max_notification_id1 = recorder.max_notification_id()
        assert isinstance(max_notification_id1, int)

        # Check notifications methods work when there aren't any.
        self.assertEqual(
            recorder.max_notification_id(),
            max_notification_id1,
        )
        self.assertEqual(
            len(
                recorder.select_notifications(
                    start=max_notification_id1,
                    limit=10,
                    inclusive_of_start=False,
                )
            ),
            0,
        )
        self.assertEqual(
            len(
                recorder.select_notifications(
                    start=max_notification_id1,
                    limit=3,
                    topics=["topic1"],
                    inclusive_of_start=False,
                )
            ),
            0,
        )

        self.assertEqual(
            len(
                recorder.select_notifications(
                    start=max_notification_id1, limit=10, inclusive_of_start=False
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
            state=b'{"state": "state1"}',
        )
        stored_event2 = StoredEvent(
            originator_id=originator_id1,
            originator_version=self.INITIAL_VERSION + 1,
            topic="topic2",
            state=b'{"state": "state2"}',
        )
        stored_event3 = StoredEvent(
            originator_id=originator_id2,
            originator_version=self.INITIAL_VERSION,
            topic="topic3",
            state=b'{"state": "state3"}',
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
        assert isinstance(max_notification_id2, int)

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
        assert isinstance(max_notification_id3, int)

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

        # InvalidPosition error when selecting from max_notification_id1 + 1.
        with self.assertRaises(kurrentdbclient.exceptions.UnknownError):  # as cm:
            recorder.select_notifications(
                max_notification_id1 + 1, 10, inclusive_of_start=False
            )
        # self.assertIn("InvalidPosition", str(cm.exception))

        # From docker.eventstore.com/eventstore-ce/eventstoredb-ce:22.10.4-jammy
        # <_MultiThreadedRendezvous of RPC that terminated with:
        # 	status = StatusCode.UNKNOWN
        # 	details = "Unexpected FilteredReadAllResult: Error"
        # 	debug_error_string = "UNKNOWN:Error received from peer  {created_time:
        # 	"2025-05-07T01:05:37.567805+01:00", grpc_status:2, grpc_message:
        # 	"Unexpected FilteredReadAllResult: Error"}"
        # >

        # From docker.eventstore.com/eventstore/eventstoredb-ee:
        #   24.10.0-x64-8.0-bookworm-slim

        # <_MultiThreadedRendezvous of RPC that terminated with:
        # 	status = StatusCode.UNKNOWN
        # 	details = "Unexpected FilteredReadAllResult: InvalidPosition"
        # 	debug_error_string = "UNKNOWN:Error received from peer  {created_time:
        # 	"2025-05-07T01:00:12.828196+01:00", grpc_status:2, grpc_message:
        # 	"Unexpected FilteredReadAllResult: InvalidPosition"}"
        # >

        notifications = recorder.select_notifications(
            max_notification_id1, 10, inclusive_of_start=False
        )
        self.assertEqual(len(notifications), 3)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[0].topic, "topic1")
        self.assertEqual(notifications[0].state, b'{"state": "state1"}')
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION + 1)
        self.assertEqual(notifications[1].topic, "topic2")
        self.assertEqual(notifications[1].state, b'{"state": "state2"}')
        self.assertEqual(notifications[1].id, max_notification_id2)

        self.assertEqual(notifications[2].originator_id, originator_id2)
        self.assertEqual(notifications[2].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[2].topic, "topic3")
        self.assertEqual(notifications[2].state, b'{"state": "state3"}')
        self.assertEqual(notifications[2].id, max_notification_id3)

        # Select notification by topic (all topics).
        notifications = recorder.select_notifications(
            max_notification_id1,
            10,
            topics=["topic1", "topic2", "topic3"],
            inclusive_of_start=False,
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
            max_notification_id1, 10, topics=["topic1"], inclusive_of_start=False
        )

        # Check we got the correct notification.
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select notification by topic (topic2 only).
        notifications = recorder.select_notifications(
            max_notification_id1, 10, topics=["topic2"], inclusive_of_start=False
        )

        # Check we got the correct notification.
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION + 1)

        # Select notification by topic (topic3 only).
        notifications = recorder.select_notifications(
            max_notification_id1, 10, topics=["topic3"], inclusive_of_start=False
        )

        # Check we got the correct notification.
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id2)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select notification by topic (topic1 and topic3 only).
        notifications = recorder.select_notifications(
            max_notification_id1,
            10,
            topics=["topic1", "topic3"],
            inclusive_of_start=False,
        )

        # Check we got the correct notifications.
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[1].originator_id, originator_id2)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION)

        # Select a limited number of notifications from initial position.
        # print("max_notification_id1:", max_notification_id1)
        notifications = recorder.select_notifications(
            start=max_notification_id1,
            limit=1,
            inclusive_of_start=False,
        )
        # for notification in notifications:
        #     print("notification:", notification)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select a limited number of notifications from later position.
        notifications = recorder.select_notifications(
            max_notification_id2, 1, inclusive_of_start=False
        )
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id2)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)

        # Select a limited number of notifications
        # from later position (inclusive of start).
        notifications = recorder.select_notifications(
            max_notification_id2, 1, inclusive_of_start=True
        )
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, 1)

        # Select notifications between two positions
        notifications = recorder.select_notifications(
            start=max_notification_id1,
            limit=10,
            stop=max_notification_id2,
            inclusive_of_start=False,
        )
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].originator_id, originator_id1)
        self.assertEqual(notifications[0].originator_version, self.INITIAL_VERSION)
        self.assertEqual(notifications[1].originator_id, originator_id1)
        self.assertEqual(notifications[1].originator_version, self.INITIAL_VERSION + 1)

        # Cover exception handling when stream name is not a UUID.
        max_notification_id4 = recorder.max_notification_id()
        assert isinstance(max_notification_id4, int)

        cast(KurrentDBApplicationRecorder, recorder).client.append_to_stream(
            stream_name=f"not-a-uuid-{uuid4()}",
            events=NewEvent(type="SomethingHappened", data=b"{}"),
            current_version=StreamState.NO_STREAM,
        )
        with self.assertRaises(ValueError) as cm1:
            recorder.select_notifications(
                start=max_notification_id4,
                limit=10,
                stop=max_notification_id2,
                inclusive_of_start=False,
            )
        self.assertIn("badly formed hexadecimal UUID string", str(cm1.exception))

        # Cover non-wrong-current-version exception handling when appending events.
        cast(KurrentDBApplicationRecorder, recorder).client.close()
        cast(KurrentDBApplicationRecorder, recorder).client.connection_spec._targets = [
            "127.0.0.1:1000"
        ]
        with self.assertRaises(PersistenceError) as cm2:
            recorder.insert_events([stored_event3])
        self.assertIn("failed to connect", str(cm2.exception))

    def test_concurrent_no_conflicts(self) -> None:
        super().test_concurrent_no_conflicts()

    def test_insert_subscribe(self) -> None:
        self.validate_uuids = True
        super().optional_test_insert_subscribe()

    def test_subscribe_concurrent_reading_and_writing(self) -> None:
        recorder = self.create_recorder()

        num_batches = 1000
        batch_size = 1
        num_events = num_batches * batch_size

        def read(last_notification_id: int | None) -> None:
            subscription = recorder.subscribe(last_notification_id)
            start = datetime_now_with_tzinfo()
            with subscription:
                for i, _ in enumerate(subscription):
                    # print("Read", i+1, "notifications")
                    # last_notification_id = notification.id
                    if i + 1 == num_events:
                        break
            duration = datetime_now_with_tzinfo() - start
            print(
                "Finished reading",
                num_events,
                "events in",
                duration.total_seconds(),
                "seconds",
            )

        def write() -> None:
            start = datetime_now_with_tzinfo()
            for _ in range(num_batches):
                originator_id = uuid4()
                events = []
                for i in range(batch_size):
                    stored_event = StoredEvent(
                        originator_id=originator_id,
                        originator_version=i,
                        topic="topic1",
                        state=b'{"state": "state1"}',
                    )
                    events.append(stored_event)
                recorder.insert_events(events)
                # print("Wrote", i + 1, "notifications")
            duration = datetime_now_with_tzinfo() - start
            print(
                "Finished writing",
                num_events,
                "events in",
                duration.total_seconds(),
                "seconds",
            )

        thread_pool = ThreadPoolExecutor(max_workers=2)

        print("Concurrent...")
        # Get the max notification ID (for the subscription).
        last_notification_id = recorder.max_notification_id()
        write_job = thread_pool.submit(write)
        read_job = thread_pool.submit(read, last_notification_id)
        write_job.result()
        read_job.result()

        print("Sequential...")
        last_notification_id = recorder.max_notification_id()
        write_job = thread_pool.submit(write)
        write_job.result()
        read_job = thread_pool.submit(read, last_notification_id)
        read_job.result()

        thread_pool.shutdown(wait=True)

    def test_str_originator_ids(self) -> None:
        self.validate_uuids = False
        recorder = self.create_recorder()

        originator_id = f"product-{uuid4()}"
        stored_event = StoredEvent(
            originator_id=originator_id,
            originator_version=0,
            topic="topic1",
            state=b'{"state": "state1"}',
        )

        recorder.insert_events([stored_event])


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
