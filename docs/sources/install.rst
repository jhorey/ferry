:title: Ferry Installation
:description: Installing Ferry on your local machine
:keywords: ferry, installation

Install
=======

Ferry is written in Python and available via ``pip``, but before we can run some
applications, we'll need to install a few prerequisites. First you'll need to install Docker. If you're running the latest version of Ubuntu, it's fairly straightforward. 

.. code-block:: bash

    $ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
    $ sudo sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
    $ sudo apt-get update
    $ sudo apt-get install lxc-docker

However, if you're running OS X or another version of Linux, you'll probably want to visit
the Docker_ homepage for more detailed instructions. 

.. _Docker: http://docs.docker.io/en/latest/installation/

After installing Docker, you'll want to create a new group called ``docker`` to simplify interacting with Docker and
Ferry as a non-root user. 

.. code-block:: bash

    $ sudo groupadd docker
    $ sudo usermod -a -G docker $USER

Make sure that Docker is running before installing the rest of Ferry. You can do that by typing in your terminal: 

.. code-block:: bash

    $ sudo service docker start
    $ docker info

You should see some versioning information printed to the screen. Next you'll want to install Ferry. 
You can do this via ``pip``. 

.. code-block:: bash

    $ sudo pip install -U ferry

If you don't have ``pip`` installed, you can also clone Ferry from the GitHub repo and manually
install the packages (look for ``setup.py``). After installing Ferry, check if everything is working 
and start building the various Ferry images. These images contain the actual logic for running Hadoop, Cassandra, etc. Just type:

.. code-block:: bash

    $ ferry info
    $ sudo ferry install

By default Ferry will use a default set of public/private keys so that you can interact with the
connectors afterwards. You can instruct ``ferry`` to use your own keys by supplying a directory like this 
``ferry install -k $KEY_DIR``. The build process may take a while, so sit back and relax. 

Once Ferry is completely installed you'll want to head over to the Getting Started documents. 
Currently Ferry supports the following backends:

- :ref:`Hadoop <hadoop>` (version 2.3.0) with Hive (version 0.12)
- :ref:`Cassandra <cassandra>` (version 2.0.5)
- :ref:`Titan graph database <cassandra>` (0.3.1)
- :ref:`Gluster Filesystem <mpi>` (version 3.4)
- :ref:`OpenMPI <mpi>` (version 1.7.3)
