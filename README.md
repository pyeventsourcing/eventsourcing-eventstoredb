# Event Sourcing in Python with EventStoreDB

This is an extension package for the Python
[eventsourcing](https://github.com/pyeventsourcing/eventsourcing) library
that provides a persistence module for [EventStoreDB](https://www.eventstore.com/).
It uses the [esdbclient](https://github.com/pyeventsourcing/esdbclient)
package to communicate with EventStoreDB via its gRPC interface.

## Installation

Use pip to install the [stable distribution](https://pypi.org/project/eventsourcing-eventstoredb/)
from the Python Package Index.

    $ pip install eventsourcing-eventstoredb

Please note, it is recommended to install Python packages into a Python virtual environment.

## Getting started

Define aggregates and applications in the usual way. Please note, aggregate
sequences  in EventStoreDB start from position `0`, so set INITIAL_VERSION
on your aggregate classes accordingly.

```python
from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event


class TrainingSchool(Application):
    def register(self, name):
        dog = Dog(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id, trick):
        dog = self.repository.get(dog_id)
        dog.add_trick(trick)
        self.save(dog)

    def get_dog(self, dog_id):
        dog = self.repository.get(dog_id)
        return {'name': dog.name, 'tricks': list(dog.tricks)}


class Dog(Aggregate):
    INITIAL_VERSION = 0

    @event('Registered')
    def __init__(self, name):
        self.name = name
        self.tricks = []

    @event('TrickAdded')
    def add_trick(self, trick):
        self.tricks.append(trick)
```

Configure the application to use EventStoreDB. Set environment variable
`PERSISTENCE_MODULE` to `'eventsourcing_eventstoredb'`, and set
`EVENTSTOREDB_URI` to the host and port of your EventStoreDB.

```python
school = TrainingSchool(env={
    'PERSISTENCE_MODULE': 'eventsourcing_eventstoredb',
    'EVENTSTOREDB_URI': 'localhost:2113',
})
```

*NB: SSL/TLS not yet supported:* In case you are running against a cluster, or want to use SSL/TLS certificates,
you can specify these things in the URI.

```
    'EVENTSTOREDB_URI': 'esdb://localhost:2111,localhost:2112,localhost:2113?tls&rootCertificate=./certs/ca/ca.crt'
```

Call application methods from tests and user interfaces.

```python
dog_id = school.register('Fido')
school.add_trick(dog_id, 'roll over')
school.add_trick(dog_id, 'play dead')
dog_details = school.get_dog(dog_id)
assert dog_details['name'] == 'Fido'
assert dog_details['tricks'] == ['roll over', 'play dead']
```

To see the events have been saved, we can reconstruct the application
and get Fido's details again.

```python
school = TrainingSchool(env={
    'PERSISTENCE_MODULE': 'eventsourcing_eventstoredb',
    'EVENTSTOREDB_URI': 'localhost:2113',
})

dog_details = school.get_dog(dog_id)

assert dog_details['name'] == 'Fido'
assert dog_details['tricks'] == ['roll over', 'play dead']
```

For more information, please refer to the Python
[eventsourcing](https://github.com/johnbywater/eventsourcing) library
and the [EventStoreDB](https://www.eventstore.com/) project.

## Developers

Clone the `eventsourcing-eventstoredb` repository, set up a virtual
environment, and install dependencies.

Use your IDE (e.g. PyCharm) to open the project repository. Create a
Poetry virtual environment, and then update packages.

    $ make update-packages

Alternatively, use the ``make install`` command to create a dedicated
Python virtual environment for this project.

    $ make install

Start EventStoreDB.

    $ make start-eventstoredb

Run tests.

    $ make test

Add tests in `./tests`. Add code in `./eventsourcing_eventstoredb`.

Check the formatting of the code.

    $ make lint

Reformat the code.

    $ make fmt

Add dependencies in `pyproject.toml` and then update installed packages.

    $ make update-packages

Stop EventStoreDB.

    $ make stop-eventstoredb
