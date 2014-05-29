:title: Ferry Basics
:description: Basic examples
:keywords: ferry, examples

.. _basics:

Quick start
===========

Let's get a basic Hadoop cluster up and running using Ferry. First you'll need to 
install Docker. If you're running the latest version of Ubuntu, it's fairly straightforward. 

.. code-block:: bash

    $ sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
    $ sudo sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
    $ sudo apt-get update
    $ sudo apt-get install lxc-docker-0.8.1

*Please note that you'll need to install Docker version 0.8.1. This will install additional libraries that Ferry needs.*

You'll also want to create a new group called ``docker`` to simplify interacting with Docker and
Ferry as a non-root user. There are more detailed instructions on the Docker_ homepage. 

.. _Docker: http://docs.docker.io/en/latest/installation/

Next you'll want to install Ferry. 

.. code-block:: bash

    $ sudo pip install -U ferry

Now you'll want to build the various Ferry images. Just type:

.. code-block:: bash

    $ sudo ferry install

This will take at least tens of minutes, so sit back and relax. After all the images are built, check by typing:

.. code-block:: bash

    $ sudo ferry server
    $ ferry info

Congratulations! 


You can examine the pre-installed Ferry applications by typing: 

.. code-block:: bash

    $ ferry ls
       App           Author       Version           Description
       ---           ------       -------           -----------
    cassandra     James Horey      0.2.0         Cassandra stack...
      hadoop      James Horey      0.2.0          Hadoop stack...
     openmpi      James Horey      0.2.0      Open MPI over Gluster...
      spark       James Horey      0.2.0        Spark over Hadoop...
       yarn       James Horey      0.2.0      Hadoop YARN over Glus...

Say you're interested in the Hadoop application, just type the following to create a new Spark cluster: 

.. code-block:: bash

    $ ferry start hadoop

At this point, you probably want to head over to the :ref:`Hadoop <hadoop>` tutorial to understand how to interact with your new cluster. 

When you're all done writing your application, you can stop the Ferry servers by typing:

.. code-block:: bash

    $ sudo ferry quit
