# -*- coding: utf-8 -*-
from esdbclient import ESDBClient
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
    EVENTSTOREDB_ROOT_CERTIFICATES = "EVENTSTOREDB_ROOT_CERTIFICATES"

    def __init__(self, env: Environment):
        super().__init__(env)
        eventstoredb_uri = self.env.get(self.EVENTSTOREDB_URI)
        if eventstoredb_uri is None:
            raise EnvironmentError(
                f"{self.EVENTSTOREDB_URI!r} not found "
                "in environment with keys: "
                f"{', '.join(self.env.create_keys(self.EVENTSTOREDB_URI))!r}"
            )
        root_certificates = self.env.get(self.EVENTSTOREDB_ROOT_CERTIFICATES)
        try:
            self.client = ESDBClient(
                uri=eventstoredb_uri,
                root_certificates=root_certificates,
            )
        except ValueError as e:
            if "root_certificates" in e.args[0]:
                raise EnvironmentError(
                    "Please configure environment variable "
                    f"'{self.EVENTSTOREDB_ROOT_CERTIFICATES}' "
                    "when connecting to a secure server."
                ) from e

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
