:title: Ferry Advanced
:description: Basic examples
:keywords: ferry, examples

.. _advanced:

Advanced Topics
===============

Creating a Dockerfile
---------------------

All connectors in Ferry can be customized and saved during runtime. However, sometimes it's nice to specify all these runtime dependencies *outside* the connector. This would let us share applications easily with others and help us organize our own applications. Fortunately for us, we can use special files called Dockerfiles to help us do this. Here's an example Dockerfile. 

.. code-block:: bash

   FROM ferry/cassandra-client
   NAME james/cassandra-examples
   RUN apt-get --yes install python-pip python-dev
   RUN pip install cassandra-driver
   RUN git clone https://github.com/opencore/cassandra-examples.git /home/ferry/cassandra-examples

Let's take a look line by line. The first states that 

.. code-block:: bash

   FROM ferry/cassandra-client

That just means that our client is based on the official Ferry ``cassandra`` client. This ensures that all the right drivers, etc. will be automatically installed. The ``cassandra`` client, in turn, is based on an Ubuntu 12.04 image, so you can use convenient tools like ``apt-get`` in the Dockerfile. The next line:

.. code-block:: bash

   NAME james/cassandra-examples

specifies the official name of this Dockerfile (for those that have created Dockerfiles before, you may recognize that the ``NAME`` command is not an officially supported Docker command). Now the next few lines tells Ferry what to install:

.. code-block:: bash

   RUN apt-get --yes install python-pip python-dev
   RUN pip install cassandra-driver

In our case, we just want to use the Python Cassandra driver. Finally, we're going to download a copy of some convenient Cassandra examples from GitHub. 

.. code-block:: bash

   RUN git clone https://github.com/opencore/cassandra-examples.git /home/ferry/cassandra-examples

Once you have the Dockerfile specified, you can use it in a Ferry application by specifying it's name in the ``connector`` section. Here's an example:

.. code-block:: yaml

   backend:
      - storage:
           personality: "cassandra"
           instances: 2
   connectors:
      - personality: "james/cassandra-examples"

Let's assume that your ``yaml`` file is called ``cassandra_examples.yml`` and stored in the directory ``~/my_app``. In order to start your new custom application, just type the following:

.. code-block:: bash

   $ ferry start ~/my_app/cassandra_examples.yml -b ~/my_app

The ``-b`` flag tells Ferry where to find your Dockerfile. Without that flag, it won't be able to compile the ``james/cassandra-examples`` image. After you type that command the first time, you can omit the the ``-b`` flag (since the compiled image will reside on your local Ferry repository). Once you log into your connector, you find the Cassandra example applications like this:

.. code-block:: bash

   $ su ferry
   $ ls /home/ferry/cassandra-examples
   sensorapp
   twissandra
   kairosdb

Creating a Dockerfile for your application is a convenient way to store and share your application. By providing the Dockerfile (along with any files that are included in the Dockerfile), any user can run the same application in Ferry. 
