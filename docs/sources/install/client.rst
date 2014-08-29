:title: Ferry Installation
:description: Installing Ferry on your local machine
:keywords: ferry, installation

.. _client:

Install
=======

Ferry currently relies on a relatively new version of Linux (Ubuntu 13.10 and 14.04 have both been tested). While other distros will probably work, these instructions are not guaranteed to work on those environments. If you decide to go ahead and try anyway, please let us know how it went and file any issues on Github!

OS X
----

The easiest way to get started on OS X is via Vagrant_. In theory you could create an Ubuntu VM yourself and install everything (via the Ubuntu instructions), but using Vagrant is much easier. 

.. _Vagrant: http://www.vagrantup.com/

Assuming you're running Vagrant, type the following into your prompt:

.. code-block:: bash

    $ vagrant box add opencore/ferry https://s3.amazonaws.com/opencore/ferry.box
    $ vagrant init opencore/ferry
    $ vagrant up

This will create your Vagrant box and initialize everything. Please note that the Ferry box is about 3 GB, so the download will take a while (the box contains all the Docker images pre-built). After the Vagrant box is up and running, *ssh* into it:

.. code-block:: bash

    $ vagrant ssh

Now you can get :ref:`started <GettingStarted>`. Please note that this Vagrant box does not contain very much besides the basic Ferry installation, so you'll probably want to install your favorite text editor, etc.

Ubuntu
------

There are two ways to install Ferry in Linux. The first via `pip` will install Ferry in your local environment. The second is via Docker-in-Docker, in which
Ferry will install and run itself in a self-enclosed Docker container. This method is described :ref:`here <alternative>`

If you are upgrading from a prior installation, head over :ref:`here <upgrade>` for a more in-depth explanation. 

If you choose to install via ``pip`` you want to make sure that you're running Python2 (Python3 is currently not supported). The easiest way to get ``pip`` installed is by typing:

.. code-block:: bash

    $ sudo apt-get install python-pip

Afterwards we'll need to install Docker.

.. code-block:: bash

    $ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
    $ sudo sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
    $ sudo apt-get update
    $ sudo apt-get install lxc-docker-0.8.1

*Please note that you'll need to install Docker version 0.8.1. This will install additional libraries that Ferry needs.*

If you'd like a more in-depth explanation of what's going on, visit the Docker_ homepage for more detailed instructions. 

.. _Docker: http://docs.docker.io/en/latest/installation/

After installing Docker, you'll want to create a new group called ``docker`` to simplify interacting with Docker and
Ferry as a non-root user. 

.. code-block:: bash

    $ sudo groupadd docker
    $ sudo usermod -a -G docker $USER

You may need to logout and log back in for the group changes to take effect.
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

    $ sudo ferry install

By default Ferry will use a default set of public/private keys so that you can interact with the
connectors afterwards. You can instruct ``ferry`` to use your own keys by supplying a directory like this 
``ferry install -k $KEY_DIR``. The build process may take a while, so sit back and relax. 

Running Ferry
-------------

.. _GetStarted:

Once Ferry is completely installed, you should be able to start the Ferry server and start writing
your application. First you'll need to start the server. 

.. code-block:: bash

    $ sudo ferry server
    $ ferry info

Congratulations! Now you'll want to head over to the Getting Started documents to figure out how to write a big
data application. Currently Ferry supports the following backends:

- :ref:`Hadoop <hadoop>` (version 2.3.0) with Hive (version 0.12)
- :ref:`Cassandra <cassandra>` (version 2.0.5)
- :ref:`Titan graph database <cassandra>` (0.3.1)
- :ref:`Gluster Filesystem <mpi>` (version 3.4)
- :ref:`Open MPI <mpi>` (version 1.7.3)

When you're all done writing your application, you can stop the Ferry servers by typing:

.. code-block:: bash

    $ sudo ferry quit
