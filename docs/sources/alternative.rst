:title: Ferry Alternative Installation
:description: Installing Ferry on your local machine
:keywords: ferry, installation, docker

Alternative Install
===================

Ferry can also be installed completely within Docker (Docker-in-Docker). The advantage
to this method is that you don't need any specific version of Python or worry about any
additional dependencies. It may also be a bit easier if you already have a Docker
environment set up. 

To get started, you'll need to have Docker installed. Since we're running Docker-in-Docker, you'll need at least version `0.6.0`. Here are the instructions for Ubuntu. 

.. code-block:: bash

    $ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
    $ sudo sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
    $ sudo apt-get update
    $ sudo apt-get install lxc-docker

If you need to install Docker in another OS, you'll probably want to visit
the Docker_ homepage for more detailed instructions.

.. _Docker: http://docs.docker.io/en/latest/installation/

Now you need to grab a copy of the Ferry source. The easiest way is via GitHub. 

.. code-block:: bash

    $ git clone https://github.com/opencore/ferry.git

If you take a peek inside, you'll find a directory called `ferry-dockerfile`. 

.. code-block:: bash

    $ cd ferry/ferry-dockerfile
    $ ls
    make.sh
    Dockerfile

The `make.sh` is a simple shell script containing the instructions for actually
building and using the `Dockerfile`. Run it like this:

.. code-block:: bash

    $ ./make.sh install

This will first build an image called `ferry/ferry-server`. Afterwards it will
automatically begin building the various Ferry images *inside* the ferry-server. 
This process should take a while. 

If something goes wrong during this process (your computer powered off, etc.), 
you can restart the installation process by typing:


.. code-block:: bash

    $ ./make.sh install -u

You'll eventually see a message like `ferry installed` printed to the screen. 
Afterwards log into your Ferry environment by typing:

.. code-block:: bash

    $ ./make.sh start

This will log you into a container and drop you at a root prompt. Now you should
be able to start using Ferry. Type the following:

.. code-block:: bash

    $ ferry server
    $ ferry info

Congratulations! Now you'll want to head over to the Getting Started documents to figure out how to write a big
data application. Currently Ferry supports the following backends:

- :ref:`Hadoop <hadoop>` (version 2.3.0) with Hive (version 0.12)
- :ref:`Cassandra <cassandra>` (version 2.0.5)
- :ref:`Titan graph database <cassandra>` (0.3.1)
- :ref:`Gluster Filesystem <mpi>` (version 3.4)
- :ref:`OpenMPI <mpi>` (version 1.7.3)

When you're all done writing your application, you can stop the Ferry servers by typing:

.. code-block:: bash

    $ sudo ferry quit
