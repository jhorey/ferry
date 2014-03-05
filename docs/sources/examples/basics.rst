:title: Drydock Basics
:description: Basic examples
:keywords: drydock, examples

.. _basics:

Quick start
===========

Let's get a basic Hadoop cluster up and running using Drydock. First you'll need to 
install Docker. If you're running the latest version of Ubuntu, it's fairly straightforward. 

.. code-block:: bash

    $ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
    $ sudo sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
    $ sudo apt-get update
    $ sudo apt-get install lxc-docker

You'll also want to create a new group called ``docker`` to simplify interacting with Docker and
Drydock as a non-root user. There are more detailed instructions on the Docker_ homepage. 

.. _Docker: http://docs.docker.io/en/latest/installation/

Next you'll want to install Drydock. 

.. code-block:: bash

    $ sudo pip install -U drydock

Now you'll want to start the ``drydock`` daemon by typing:

.. code-block:: bash

    $ sudo drydock -d

Once the daemon is running, you'll need to build the various Drydock images.
These images contain the actual logic for running Hadoop, Cassandra, etc. Now as
either using ``sudo`` or as a ``docker`` user, in a separate terminal type:

.. code-block:: bash

    $ drydock -i

This will automatically build everything you need. This may take a while, so
sit back and relax. 

After all the images are built, head over to the :ref:`Hadoop <hadoop>` tutorial to create
a brand new Hadoop cluster.
