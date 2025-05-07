import os

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    ProcessRecorder,
    TrackingRecorder,
)
from eventsourcing.tests.persistence import InfrastructureFactoryTestCase
from eventsourcing.utils import Environment

from eventsourcing_kurrentdb.factory import KurrentDBFactory
from eventsourcing_kurrentdb.recorders import (
    KurrentDBAggregateRecorder,
    KurrentDBApplicationRecorder,
)
from tests.common import INSECURE_CONNECTION_STRING


class TestFactory(InfrastructureFactoryTestCase[KurrentDBFactory]):
    def test_create_process_recorder(self) -> None:
        self.skipTest("KurrentDB doesn't support tracking records")

    def expected_factory_class(self) -> type[KurrentDBFactory]:
        return KurrentDBFactory

    def expected_aggregate_recorder_class(self) -> type[AggregateRecorder]:
        return KurrentDBAggregateRecorder

    def expected_application_recorder_class(self) -> type[ApplicationRecorder]:
        return KurrentDBApplicationRecorder

    def expected_tracking_recorder_class(self) -> type[TrackingRecorder]:
        raise NotImplementedError

    def tracking_recorder_subclass(self) -> type[TrackingRecorder]:
        raise NotImplementedError

    def test_create_tracking_recorder(self) -> None:
        self.skipTest("KurrentDB doesn't support tracking records")

    def expected_process_recorder_class(self) -> type[ProcessRecorder]:
        raise NotImplementedError

    def setUp(self) -> None:
        self.env = Environment("TestCase")
        self.env[InfrastructureFactory.PERSISTENCE_MODULE] = KurrentDBFactory.__module__
        self.env[KurrentDBFactory.KURRENTDB_URI] = INSECURE_CONNECTION_STRING
        super().setUp()

    def tearDown(self) -> None:
        if KurrentDBFactory.KURRENTDB_URI in os.environ:
            del os.environ[KurrentDBFactory.KURRENTDB_URI]
        super().tearDown()


del InfrastructureFactoryTestCase
