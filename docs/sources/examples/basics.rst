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

This may take a while, so sit back and relax. After all the images are built, head over to the 
:ref:`Hadoop <hadoop>` tutorial to create a brand new Hadoop cluster.
