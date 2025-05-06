from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    InfrastructureFactoryError,
    ProcessRecorder,
    TrackingRecorder,
)
from kurrentdbclient import KurrentDBClient

from eventsourcing_eventstoredb.recorders import (
    EventStoreDBAggregateRecorder,
    EventStoreDBApplicationRecorder,
)

if TYPE_CHECKING:
    from eventsourcing.utils import Environment


class EventStoreDBFactory(InfrastructureFactory[TrackingRecorder]):
    """
    Infrastructure factory for EventStoreDB infrastructure.
    """

    EVENTSTOREDB_URI = "EVENTSTOREDB_URI"
    EVENTSTOREDB_ROOT_CERTIFICATES = "EVENTSTOREDB_ROOT_CERTIFICATES"

    def __init__(self, env: Environment):
        super().__init__(env)
        eventstoredb_uri = self.env.get(self.EVENTSTOREDB_URI)
        if eventstoredb_uri is None:
            msg = (
                f"{self.EVENTSTOREDB_URI!r} not found "
                "in environment with keys: "
                f"{', '.join(self.env.create_keys(self.EVENTSTOREDB_URI))!r}"
            )
            raise InfrastructureFactoryError(msg)
        root_certificates = self.env.get(self.EVENTSTOREDB_ROOT_CERTIFICATES)
        self.client = KurrentDBClient(
            uri=eventstoredb_uri,
            root_certificates=root_certificates,
        )

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        return EventStoreDBAggregateRecorder(
            client=self.client,
            for_snapshotting=bool(purpose == "snapshots"),
        )

    def application_recorder(self) -> ApplicationRecorder:
        return EventStoreDBApplicationRecorder(self.client)

    def tracking_recorder(
        self, tracking_recorder_class: type[TrackingRecorder] | None = None
    ) -> TrackingRecorder:
        raise NotImplementedError

    def process_recorder(self) -> ProcessRecorder:
        raise NotImplementedError

    def __del__(self) -> None:
        if hasattr(self, "client"):
            del self.client
            # self.client.close()
