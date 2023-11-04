# -*- coding: utf-8 -*-
import os
from decimal import Decimal
from itertools import chain
from uuid import uuid4

from eventsourcing.application import Application, EventSourcedLog
from eventsourcing.domain import Aggregate, DomainEvent
from eventsourcing.system import NotificationLogReader
from eventsourcing.tests.application import (
    TIMEIT_FACTOR,
    BankAccounts,
    ExampleApplicationTestCase,
)
from eventsourcing.tests.domain import BankAccount
from eventsourcing.utils import get_topic

from tests.common import INSECURE_CONNECTION_STRING


class TestApplicationWithEventStoreDB(ExampleApplicationTestCase):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing_eventstoredb.factory:Factory"

    def setUp(self) -> None:
        self.original_initial_version = Aggregate.INITIAL_VERSION
        Aggregate.INITIAL_VERSION = 0
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing_eventstoredb"
        os.environ["EVENTSTOREDB_URI"] = INSECURE_CONNECTION_STRING

    def tearDown(self) -> None:
        Aggregate.INITIAL_VERSION = self.original_initial_version
        try:
            del os.environ["PERSISTENCE_MODULE"]
        except KeyError:
            pass
        try:
            del os.environ["EVENTSTOREDB_URI"]
        except KeyError:
            pass
        super().tearDown()

    def test_example_application(self) -> None:
        app = BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})

        # Check the factory topic.
        self.assertEqual(get_topic(type(app.factory)), self.expected_factory_topic)

        # Get the commit position before writing any events.
        max_notification_id1 = app.recorder.max_notification_id()

        # Select notifications.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 0)

        # Check AccountNotFound exception.
        with self.assertRaises(BankAccounts.AccountNotFoundError):
            app.get_account(uuid4())

        # Open an account.
        account_id1 = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id1),
            Decimal("0.00"),
        )

        # Get the commit position after writing one event.
        max_notification_id2 = app.recorder.max_notification_id()

        # Check there is one notification since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 1)

        # Check there are zero notifications since the second commit position.
        notifications = app.notification_log.select(max_notification_id2 + 1, 10)
        self.assertEqual(len(notifications), 0)

        # Credit the account.
        app.credit_account(account_id1, Decimal("10.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id1),
            Decimal("10.00"),
        )

        # Get the commit position after writing two events.
        max_notification_id3 = app.recorder.max_notification_id()

        # Check there are two notifications since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 2)

        # Check there is one notification since the second commit position.
        notifications = app.notification_log.select(max_notification_id2 + 1, 10)
        self.assertEqual(len(notifications), 1)

        # Check there are zero notifications since the third commit position.
        notifications = app.notification_log.select(max_notification_id3 + 1, 10)
        self.assertEqual(len(notifications), 0)

        # Credit the account twice
        app.credit_account(account_id1, Decimal("25.00"))
        app.credit_account(account_id1, Decimal("30.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id1),
            Decimal("65.00"),
        )

        # Get the commit position after writing four events.
        max_notification_id4 = app.recorder.max_notification_id()

        # Check there are four notifications since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 4)

        # Check there are three notifications since the second commit position.
        notifications = app.notification_log.select(max_notification_id2 + 1, 10)
        self.assertEqual(len(notifications), 3)

        # Check there are two notifications since the third commit position.
        notifications = app.notification_log.select(max_notification_id3 + 1, 10)
        self.assertEqual(len(notifications), 2)

        # Check there are zero notifications since the fourth commit position.
        notifications = app.notification_log.select(max_notification_id4 + 1, 10)
        self.assertEqual(len(notifications), 0)

        # Get historical version.
        account: BankAccount = app.repository.get(account_id1, version=1)
        self.assertEqual(account.version, 1)
        self.assertEqual(account.balance, Decimal("10.00"))

        # Take snapshot (don't specify version).
        app.take_snapshot(account_id1)
        assert app.snapshots
        snapshots = list(app.snapshots.get(account_id1))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, Aggregate.INITIAL_VERSION + 3)

        # Get historical version again (this won't use snapshots).
        historical_account: BankAccount = app.repository.get(account_id1, version=1)
        self.assertEqual(historical_account.version, 1)

        # Get current version (this will use snapshots).
        from_snapshot: BankAccount = app.repository.get(account_id1)
        self.assertIsInstance(from_snapshot, BankAccount)
        self.assertEqual(from_snapshot.version, Aggregate.INITIAL_VERSION + 3)
        self.assertEqual(from_snapshot.balance, Decimal("65.00"))

        # Take snapshot (specify earlier version).
        app.take_snapshot(account_id1, version=1)
        app.take_snapshot(account_id1, version=2)
        snapshots = list(app.snapshots.get(account_id1))

        # Shouldn't have recorded historical snapshot (would append old after new).
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].originator_version, Aggregate.INITIAL_VERSION + 3)

        # Check there are four notifications since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 4)

        # Check there are three notifications since the second commit position.
        notifications = app.notification_log.select(max_notification_id2 + 1, 10)
        self.assertEqual(len(notifications), 3)

        # Check there are two notifications since the third commit position.
        notifications = app.notification_log.select(max_notification_id3 + 1, 10)
        self.assertEqual(len(notifications), 2)

        # Check there are zero notifications since the fourth commit position.
        notifications = app.notification_log.select(max_notification_id4 + 1, 10)
        self.assertEqual(len(notifications), 0)

        # Open another account.
        account_id2 = app.open_account(
            full_name="Bob",
            email_address="bob@example.com",
        )
        # Credit the account three times.
        app.credit_account(account_id2, Decimal("10.00"))
        app.credit_account(account_id2, Decimal("25.00"))
        app.credit_account(account_id2, Decimal("30.00"))

        # Snapshot the account.
        app.take_snapshot(account_id2)

        # Check there are eight notifications since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 8)

        # Check the individual notifications.
        self.assertEqual(notifications[0].originator_id, account_id1)
        self.assertEqual(notifications[0].originator_version, 0)
        self.assertTrue(notifications[0].topic.endswith("BankAccount.Opened"))
        self.assertEqual(notifications[0].id, max_notification_id2)
        self.assertEqual(notifications[1].originator_id, account_id1)
        self.assertEqual(notifications[1].originator_version, 1)
        self.assertTrue(notifications[1].topic.endswith("TransactionAppended"))
        self.assertEqual(notifications[1].id, max_notification_id3)
        self.assertEqual(notifications[2].originator_id, account_id1)
        self.assertEqual(notifications[2].originator_version, 2)
        self.assertTrue(notifications[2].topic.endswith("TransactionAppended"))
        self.assertEqual(notifications[3].originator_id, account_id1)
        self.assertEqual(notifications[3].originator_version, 3)
        self.assertTrue(notifications[3].topic.endswith("TransactionAppended"))
        self.assertEqual(notifications[3].id, max_notification_id4)
        self.assertEqual(notifications[4].originator_id, account_id2)
        self.assertEqual(notifications[4].originator_version, 0)
        self.assertTrue(notifications[4].topic.endswith("BankAccount.Opened"))
        self.assertEqual(notifications[5].originator_id, account_id2)
        self.assertEqual(notifications[5].originator_version, 1)
        self.assertTrue(notifications[5].topic.endswith("TransactionAppended"))
        self.assertEqual(notifications[6].originator_id, account_id2)
        self.assertEqual(notifications[6].originator_version, 2)
        self.assertTrue(notifications[6].topic.endswith("TransactionAppended"))
        self.assertEqual(notifications[7].originator_id, account_id2)
        self.assertEqual(notifications[7].originator_version, 3)
        self.assertTrue(notifications[7].topic.endswith("TransactionAppended"))

        # Open another account.
        account_id3 = app.open_account(
            full_name="Bob",
            email_address="bob@example.com",
        )
        # Credit the account three times.
        app.credit_account(account_id3, Decimal("10.00"))
        app.credit_account(account_id3, Decimal("25.00"))
        app.credit_account(account_id3, Decimal("30.00"))

        # Check we can get five notifications since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 5)
        self.assertEqual(len(notifications), 5)

        # Check we can get ten notifications since the initial commit position.
        notifications = app.notification_log.select(max_notification_id1 + 1, 10)
        self.assertEqual(len(notifications), 10)

        # Check we can read all notification since the initial commit position.
        reader = NotificationLogReader(app.notification_log)
        notifications = list(reader.read(start=max_notification_id1 + 1))
        self.assertEqual(len(notifications), 12)

        # Check we can select all notification since the initial commit position.
        reader = NotificationLogReader(app.notification_log)
        notifications = list(chain(*reader.select(start=max_notification_id1 + 1)))
        self.assertEqual(len(notifications), 12)

    def test_event_sourced_log(self) -> None:
        class LoggedEvent(DomainEvent):
            name: str

        app = Application()
        log = EventSourcedLog(
            events=app.events,
            originator_id=uuid4(),
            logged_cls=LoggedEvent,
        )
        event = log.trigger_event(name="name1")
        app.save(event)

        events = list(log.get())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "name1")

        event = log.trigger_event(name="name2")
        app.save(event)

        events = list(log.get())
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].name, "name1")
        self.assertEqual(events[1].name, "name2")

    def test_construct_without_uri(self) -> None:
        del os.environ["EVENTSTOREDB_URI"]
        with self.assertRaises(EnvironmentError) as cm:
            BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})
        self.assertIn("EVENTSTOREDB_URI", str(cm.exception))

    def test_construct_secure_without_root_certificates(self) -> None:
        os.environ["EVENTSTOREDB_URI"] = "esdb://localhost"
        with self.assertRaises(EnvironmentError) as cm:
            BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})
        self.assertIn("EVENTSTOREDB_ROOT_CERTIFICATES", str(cm.exception))


del ExampleApplicationTestCase
