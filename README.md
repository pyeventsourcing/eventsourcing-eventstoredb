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

Define aggregates and applications in the usual way. Please note, "streams"
in EventStoreDB are constrained to start from position `0`, and this package
expects the `originator_version` of the first event in an aggregate sequence
to be `0`, so you must set `INITIAL_VERSION` on your aggregate classes to `0`.

```python
from __future__ import annotations

from uuid import uuid5, NAMESPACE_URL
from typing import List, TypedDict, Tuple

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event


class TrainingSchool(Application):
    def register(self, name: str) -> int:
        dog = Dog(name)
        recordings = self.save(dog)
        return recordings[-1].notification.id

    def add_trick(self, name: str, trick: str) -> int:
        dog = self._get_dog(name)
        dog.add_trick(trick)
        recordings = self.save(dog)
        return recordings[-1].notification.id

    def get_dog_details(self, name: str) -> DogDetails:
        dog = self._get_dog(name)
        return {'name': dog.name, 'tricks': tuple(dog.tricks)}

    def _get_dog(self, name: str) -> Dog:
        return self.repository.get(Dog.create_id(name))



class Dog(Aggregate):
    INITIAL_VERSION = 0  # for EventStoreDB

    @staticmethod
    def create_id(name: str):
        return uuid5(NAMESPACE_URL, f"/dogs/{name}")

    @event('Registered')
    def __init__(self, name):
        self.name = name
        self.tricks: List[str] = []

    @event('TrickAdded')
    def add_trick(self, trick):
        self.tricks.append(trick)


class DogDetails(TypedDict):
    name: str
    tricks: Tuple[str, ...]
```

Configure the `TrainingSchool` application to use EventStoreDB by setting the
environment variable `PERSISTENCE_MODULE` to `'eventsourcing_eventstoredb'`. You
can do this in actual environment variables, or by passing in an `env` argument when
constructing  the application object, or by setting `env` on the application class.

```python
import os

os.environ['TRAININGSCHOOL_PERSISTENCE_MODULE'] = 'eventsourcing_eventstoredb'
```

Also set environment variable `EVENTSTOREDB_URI` and to an EventStoreDB
connection string URI. This value will be used as the `uri`
argument when the `ESDBClient` class is constructed by this package.

```python
os.environ['EVENTSTOREDB_URI'] = 'esdb://localhost:2113?Tls=false'
```

If you are connecting to a "secure" EventStoreDB server, unless the
root certificate of the certificate authority used to generate the
server's certificate is installed locally, then also set environment
variable `EVENTSTOREDB_ROOT_CERTIFICATES` to an SSL/TLS certificate
suitable for making a secure gRPC connection to the EventStoreDB server(s).
This value will be used as the `root_certificates` argument when the
`ESDBClient` class is constructed by this package.


```python
os.environ['EVENTSTOREDB_ROOT_CERTIFICATES'] = '<PEM encoded SSL/TLS root certificates>'
```

Please refer to the [esdbclient](https://github.com/pyeventsourcing/esdbclient)
documentation for details about starting a "secure" or "insecure" EventStoreDB
server, the "esdb" and "esdb+discover" EventStoreDB connection string
URI schemes, and how to obtain a suitable SSL/TLS certificate for use
in the client when connecting to a "secure" EventStoreDB server.

Construct the application.

```python
training_school = TrainingSchool()
```

Call application methods from tests and user interfaces.

```python
training_school.register('Fido')
training_school.add_trick('Fido', 'roll over')
training_school.add_trick('Fido', 'play dead')
dog_details = training_school.get_dog_details('Fido')
assert dog_details['name'] == 'Fido'
assert dog_details['tricks'] == ('roll over', 'play dead')
```

To see the events have been saved, we can reconstruct the application
and get Fido's details again.

```python
training_school = TrainingSchool()

dog_details = training_school.get_dog_details('Fido')

assert dog_details['name'] == 'Fido'
assert dog_details['tricks'] == ('roll over', 'play dead')
```

## Eventually-consistent materialised views

To project the state of an event-sourced application "write model" into a
materialised view "read model", first define an interface for the materialised view
using the `TrackingRecorder` class from the `eventsourcing` library.

The example below defines methods to counts dogs and tricks for the `TrainingSchool`
application

```python
from abc import abstractmethod
from eventsourcing.persistence import Tracking, TrackingRecorder

class MaterialisedViewInterface(TrackingRecorder):
    @abstractmethod
    def incr_dog_counter(self, tracking: Tracking) -> None:
        pass

    @abstractmethod
    def incr_trick_counter(self, tracking: Tracking) -> None:
        pass

    @abstractmethod
    def get_dog_counter(self) -> int:
        pass

    @abstractmethod
    def get_trick_counter(self) -> int:
        pass
```

The `MaterialisedViewInterface` can be implemented to use a concrete database.

The example below counts dogs and tricks in memory, using "plain old Python objects".

```python
from eventsourcing.popo import POPOTrackingRecorder

class InMemoryMaterialiseView(POPOTrackingRecorder, MaterialisedViewInterface):
    def __init__(self):
        super().__init__()
        self._dog_counter = 0
        self._trick_counter = 0

    def incr_dog_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._insert_tracking(tracking)
            self._dog_counter += 1

    def incr_trick_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._insert_tracking(tracking)
            self._trick_counter += 1

    def get_dog_counter(self) -> int:
        return self._dog_counter

    def get_trick_counter(self) -> int:
        return self._trick_counter
```

Define how events will be processed using the `Projection` class from the `eventsourcing` library.

The example below processes `Dog` events. The `Dog.Registered` events are processed
by calling `incr_dog_counter()` on the materialised view. The `Dog.TrickAdded` events
are processed by calling `incr_trick_counter()`.

```python
from eventsourcing.domain import DomainEventProtocol
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.projection import Projection
from eventsourcing.utils import get_topic


class CountProjection(Projection[MaterialisedViewInterface]):
    topics = (
        get_topic(Dog.Registered),
        get_topic(Dog.TrickAdded),
    )

    @singledispatchmethod
    def process_event(self, event: DomainEventProtocol, tracking: Tracking) -> None:
        pass

    @process_event.register
    def dog_registered(self, event: Dog.Registered, tracking: Tracking) -> None:
        self.view.incr_dog_counter(tracking)

    @process_event.register
    def trick_added(self, event: Dog.TrickAdded, tracking: Tracking) -> None:
        self.view.incr_trick_counter(tracking)
```

Run the projection with the `ProjectionRunner` class from the `eventsourcing` library.

The example below shows that when the projection is run, the materialised view is updated
by processing the event of the upstream event-sourced `TrainingSchool` application. It
also shows that when tricks are subsequently added to the application's aggregates,
events continue to be processed, such that the trick counter is incremented in the
downstream materialised view "read model".

```python
import os
from eventsourcing.projection import ProjectionRunner

with ProjectionRunner(
    application_class=TrainingSchool,
    projection_class=CountProjection,
    view_class=InMemoryMaterialiseView,
) as runner:

    # Get "read model" instance from runner, because
    # state of materialised view is stored in memory.
    materialised_view = runner.projection.view

    # Wait for the existing events to be processed.
    materialised_view.wait(
        application_name=training_school.name,
        notification_id=training_school.recorder.max_notification_id(),
    )

    # Query the "read model".
    dog_count = materialised_view.get_dog_counter()
    trick_count = materialised_view.get_trick_counter()

    # Record another event in "write model".
    notification_id = training_school.add_trick('Fido', 'sit and stay')

    # Wait for the new event to be processed.
    materialised_view.wait(
        application_name=training_school.name,
        notification_id=notification_id,
    )

    # Expect one trick more, same number of dogs.
    assert dog_count == materialised_view.get_dog_counter()
    assert trick_count + 1 == materialised_view.get_trick_counter()

    # Write another event.
    notification_id = training_school.add_trick('Fido', 'jump hoop')

    # Wait for the new event to be processed.
    materialised_view.wait(
        training_school.name,
        notification_id,
    )

    # Expect two tricks more, same number of dogs.
    assert dog_count == materialised_view.get_dog_counter()
    assert trick_count + 2 == materialised_view.get_trick_counter()
```

See the Python `eventsourcing` package documentation for more information about
projecting the state of an event-sourced application into materialised views
that use a durable database such as SQLite and PostgreSQL.

## More information

For more information, please refer to the Python
[eventsourcing](https://github.com/pyeventsourcing/eventsourcing) library, the
Python [esdbclient](https://github.com/pyeventsourcing/esdbclient) package,
and the [EventStoreDB](https://www.eventstore.com/) project.

## Contributors

### Install Poetry

The first thing is to check you have Poetry installed.

    $ poetry --version

If you don't, then please [install Poetry](https://python-poetry.org/docs/#installing-with-the-official-installer).

It will help to make sure Poetry's bin directory is in your `PATH` environment variable.

But in any case, make sure you know the path to the `poetry` executable. The Poetry
installer tells you where it has been installed, and how to configure your shell.

Please refer to the [Poetry docs](https://python-poetry.org/docs/) for guidance on
using Poetry.

### Setup for PyCharm users

You can easily obtain the project files using PyCharm (menu "Git > Clone...").
PyCharm will then usually prompt you to open the project.

Open the project in a new window. PyCharm will then usually prompt you to create
a new virtual environment.

Create a new Poetry virtual environment for the project. If PyCharm doesn't already
know where your `poetry` executable is, then set the path to your `poetry` executable
in the "New Poetry Environment" form input field labelled "Poetry executable". In the
"New Poetry Environment" form, you will also have the opportunity to select which
Python executable will be used by the virtual environment.

PyCharm will then create a new Poetry virtual environment for your project, using
a particular version of Python, and also install into this virtual environment the
project's package dependencies according to the `pyproject.toml` file, or the
`poetry.lock` file if that exists in the project files.

You can add different Poetry environments for different Python versions, and switch
between them using the "Python Interpreter" settings of PyCharm. If you want to use
a version of Python that isn't installed, either use your favourite package manager,
or install Python by downloading an installer for recent versions of Python directly
from the [Python website](https://www.python.org/downloads/).

Once project dependencies have been installed, you should be able to run tests
from within PyCharm (right-click on the `tests` folder and select the 'Run' option).

Because of a conflict between pytest and PyCharm's debugger and the coverage tool,
you may need to add ``--no-cov`` as an option to the test runner template. Alternatively,
just use the Python Standard Library's ``unittest`` module.

You should also be able to open a terminal window in PyCharm, and run the project's
Makefile commands from the command line (see below).

### Setup from command line

Obtain the project files, using Git or suitable alternative.

In a terminal application, change your current working directory
to the root folder of the project files. There should be a Makefile
in this folder.

Use the Makefile to create a new Poetry virtual environment for the
project and install the project's package dependencies into it,
using the following command.

    $ make install-packages

It's also possible to also install the project in 'editable mode'.

    $ make install

Please note, if you create the virtual environment in this way, and then try to
open the project in PyCharm and configure the project to use this virtual
environment as an "Existing Poetry Environment", PyCharm sometimes has some
issues (don't know why) which might be problematic. If you encounter such
issues, you can resolve these issues by deleting the virtual environment
and creating the Poetry virtual environment using PyCharm (see above).

### Project Makefile commands

You can start EventStoreDB using the following command.

    $ make start-eventstoredb

You can run tests using the following command (needs EventStoreDB to be running).

    $ make test

You can stop EventStoreDB using the following command.

    $ make stop-eventstoredb

You can check the formatting of the code using the following command.

    $ make lint

You can reformat the code using the following command.

    $ make fmt

Tests belong in `./tests`. Code-under-test belongs in `./eventsourcing_eventstoredb`.

Edit package dependencies in `pyproject.toml`. Update installed packages (and the
`poetry.lock` file) using the following command.

    $ make update-packages
