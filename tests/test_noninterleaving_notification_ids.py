# -*- coding: utf-8 -*-
from eventsourcing.persistence import ApplicationRecorder
from eventsourcing.tests.persistence import NonInterleavingNotificationIDsBaseCase
from kurrentdbclient import KurrentDBClient

from eventsourcing_eventstoredb.recorders import EventStoreDBApplicationRecorder
from tests.common import INSECURE_CONNECTION_STRING


class TestNonInterleaving(NonInterleavingNotificationIDsBaseCase):
    insert_num = 1000

    def setUp(self) -> None:
        super().setUp()
        self.client = KurrentDBClient(INSECURE_CONNECTION_STRING)

    def tearDown(self) -> None:
        del self.client

    def create_recorder(self) -> ApplicationRecorder:
        return EventStoreDBApplicationRecorder(client=self.client)


del NonInterleavingNotificationIDsBaseCase
