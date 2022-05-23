# -*- coding: utf-8 -*-
from unittest import skip

from esdbclient.client import EsdbClient
from eventsourcing.persistence import ApplicationRecorder
from eventsourcing.tests.persistence import NonInterleavingNotificationIDsBaseCase

from eventsourcing_eventstoredb.recorders import EventStoreDBApplicationRecorder

from .common import INSECURE_CONNECTION_STRING


@skip("This is still a bit flakey - not sure why")
class TestNonInterleaving(NonInterleavingNotificationIDsBaseCase):
    insert_num = 1000

    def setUp(self) -> None:
        super().setUp()
        self.client = EsdbClient(INSECURE_CONNECTION_STRING)

    def tearDown(self) -> None:
        del self.client

    def create_recorder(self) -> ApplicationRecorder:
        return EventStoreDBApplicationRecorder(client=self.client)


del NonInterleavingNotificationIDsBaseCase
