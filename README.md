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
    INITIAL_VERSION = 0  # for EventStoreDB

    @event('Registered')
    def __init__(self, name):
        self.name = name
        self.tricks = []

    @event('TrickAdded')
    def add_trick(self, trick):
        self.tricks.append(trick)
```

Configure the application to use EventStoreDB by setting the application environment
variable `PERSISTENCE_MODULE` to `'eventsourcing_eventstoredb'`. You can do this
in actual environment variables, by passing in an `env` argument when constructing
the application object, or by setting `env` on the application class.

```python
import os

os.environ['PERSISTENCE_MODULE'] = 'eventsourcing_eventstoredb'
```

Also set environment variable `EVENTSTOREDB_URI` and to an EventStoreDB
connection string URI. This value will be used as the `uri`
argument when the `ESDBClient` class is constructed by this package.

```python
os.environ['EVENTSTOREDB_URI'] = 'esdb://localhost:2113?Tls=false'
```

If you are connecting to a "secure" EventStoreDB server, also set
environment variable `EVENTSTOREDB_ROOT_CERTIFICATES` to an SSL/TLS certificate
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
school = TrainingSchool()
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
school = TrainingSchool()

dog_details = school.get_dog(dog_id)

assert dog_details['name'] == 'Fido'
assert dog_details['tricks'] == ['roll over', 'play dead']
```

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
