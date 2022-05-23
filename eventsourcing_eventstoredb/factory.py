# -*- coding: utf-8 -*-
from esdbclient.client import EsdbClient
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    ProcessRecorder,
)
from eventsourcing.utils import Environment

from eventsourcing_eventstoredb.recorders import (
    EventStoreDBAggregateRecorder,
    EventStoreDBApplicationRecorder,
)


class Factory(InfrastructureFactory):
    """
    Infrastructure factory for EventStoreDB infrastructure.
    """

    EVENTSTOREDB_URI = "EVENTSTOREDB_URI"

    def __init__(self, env: Environment):
        super().__init__(env)
        eventstoredb_uri = self.env.get(self.EVENTSTOREDB_URI)
        if eventstoredb_uri is None:
            raise EnvironmentError(
                f"'{self.EVENTSTOREDB_URI}' not found "
                "in environment with keys: "
                f"'{', '.join(self.env.create_keys(self.EVENTSTOREDB_URI))}'"
            )
        self.client = EsdbClient(uri=eventstoredb_uri)

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        return EventStoreDBAggregateRecorder(
            client=self.client,
            for_snapshotting=bool(purpose == "snapshots"),
        )

    def application_recorder(self) -> ApplicationRecorder:
        return EventStoreDBApplicationRecorder(self.client)

    def process_recorder(self) -> ProcessRecorder:
        raise NotImplementedError()

    def __del__(self) -> None:
        del self.client
        # self.client.close()
