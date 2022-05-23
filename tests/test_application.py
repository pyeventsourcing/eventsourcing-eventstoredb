# -*- coding: utf-8 -*-
import os
from decimal import Decimal
from uuid import uuid4

from eventsourcing.domain import Aggregate
from eventsourcing.tests.application import (
    TIMEIT_FACTOR,
    BankAccounts,
    ExampleApplicationTestCase,
)
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
        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["EVENTSTOREDB_URI"]
        super().tearDown()

    def test_example_application(self) -> None:
        app = BankAccounts(env={"IS_SNAPSHOTTING_ENABLED": "y"})
        # max_notification_id = app.recorder.max_notification_id()

        self.assertEqual(get_topic(type(app.factory)), self.expected_factory_topic)

        # Check AccountNotFound exception.
        with self.assertRaises(BankAccounts.AccountNotFoundError):
            app.get_account(uuid4())

        # Open an account.
        account_id = app.open_account(
            full_name="Alice",
            email_address="alice@example.com",
        )

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("0.00"),
        )

        # Credit the account.
        app.credit_account(account_id, Decimal("10.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("10.00"),
        )

        app.credit_account(account_id, Decimal("25.00"))
        app.credit_account(account_id, Decimal("30.00"))

        # Check balance.
        self.assertEqual(
            app.get_balance(account_id),
            Decimal("65.00"),
        )


del ExampleApplicationTestCase
