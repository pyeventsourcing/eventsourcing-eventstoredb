# -*- coding: utf-8 -*-
import os
from typing import Type

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    ProcessRecorder,
    TrackingRecorder,
)
from eventsourcing.tests.persistence import InfrastructureFactoryTestCase
from eventsourcing.utils import Environment

from eventsourcing_eventstoredb.factory import EventStoreDBFactory
from eventsourcing_eventstoredb.recorders import (
    EventStoreDBAggregateRecorder,
    EventStoreDBApplicationRecorder,
)
from tests.common import INSECURE_CONNECTION_STRING


class TestFactory(InfrastructureFactoryTestCase[EventStoreDBFactory]):
    def test_create_process_recorder(self) -> None:
        self.skipTest("EventStoreDB doesn't support tracking records")

    def expected_factory_class(self) -> Type[EventStoreDBFactory]:
        return EventStoreDBFactory

    def expected_aggregate_recorder_class(self) -> Type[AggregateRecorder]:
        return EventStoreDBAggregateRecorder

    def expected_application_recorder_class(self) -> Type[ApplicationRecorder]:
        return EventStoreDBApplicationRecorder

    def expected_tracking_recorder_class(self) -> Type[TrackingRecorder]:
        raise NotImplementedError()

    def tracking_recorder_subclass(self) -> Type[TrackingRecorder]:
        raise NotImplementedError()

    def test_create_tracking_recorder(self) -> None:
        self.skipTest("EventStoreDB doesn't support tracking records")

    def expected_process_recorder_class(self) -> Type[ProcessRecorder]:
        raise NotImplementedError()

    def setUp(self) -> None:
        self.env = Environment("TestCase")
        self.env[InfrastructureFactory.PERSISTENCE_MODULE] = (
            EventStoreDBFactory.__module__
        )
        self.env[EventStoreDBFactory.EVENTSTOREDB_URI] = INSECURE_CONNECTION_STRING
        super().setUp()

    def tearDown(self) -> None:
        if EventStoreDBFactory.EVENTSTOREDB_URI in os.environ:
            del os.environ[EventStoreDBFactory.EVENTSTOREDB_URI]
        super().tearDown()


del InfrastructureFactoryTestCase
