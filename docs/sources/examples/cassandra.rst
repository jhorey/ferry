:title: Cassandra example
:description: A simple example using Cassandra
:keywords: drydock, example, cassandra

.. _cassandra:

Getting started with Cassandra
==============================

Cassandra is a highly scalable, "wide-column" store used to store large amounts
of semi-structured data. It is often used for applications that insert lots of
streaming data (i.e., sensors, web metrics, etc.), and where high availability is a premium. 

The first thing to do is define our stack in a file (let's call it ``cassandra.json``). 
The file should look something like this:

.. code-block:: javascript

    {
      "backend":[
       {
        "storage":
            {
  	       "personality":"cassandra",
  	       "instances":2,
  	       "args":{
	          "db":"users"
  	       }
	    }
       }], 
      "connectors":[
	    {
	       "personality":"cassandra-client",
  	       "args":{
	          "db":"users"
  	       }
	    }
      ]
    }

There are two main sections: the ``backend`` and ``connectors``. In this example, we're defining a single
``storage`` backend with two Cassandra instances. We're also specifying the name of the default 
database (``users``). We're also creating a single Cassandra client that connects to the default database. 
This client is just a Linux instance that is automatically configured to connect to Cassandra. 

Running an example
------------------

Now that we've defined our stack, let's start it up. Just type the following in your terminal:

.. code-block:: bash

   $ drydock start cassandra
   sa-0

   $ drydock ps
   UUID Storage  Compute  Connectors  Status   Base  Time
   ---- ------- --------- ---------- ------- ------- ----
   sa-0    se-0 [u'se-1']       se-2 running cassandra --

The entire process should take about 20 seconds. Before we continue, let's take a step back to 
examine what just happened. After typing ``start``, ``drydock`` created the following Docker
containers:

- Two Cassandra data nodes
- A Linux client

Now that the environment is created, let's interact with it by connecting to the Linux client. 
Just type ``docker ssh sa-0`` in your terminal. From there you'll can check your backend connection 
and install whatever you need. 

Now let's check what environment variables have been created. Remember
this is all being run from the connector. 

.. code-block:: bash

   $ env | grep BACKEND
   BACKEND_STORAGE_TYPE=cassandra
   BACKEND_STORAGE_IP=10.1.0.3

Now let's interact with Cassandra by creating a simple database. You can interact with Cassandra using ``cql``,
a language similar to SQL. 

.. code-block:: sql

    CREATE KEYSPACE mykeyspace WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 1 };

    USE mykeyspace;
    CREATE TABLE users (
      user_id int PRIMARY KEY,
      fname text,
      lname text
    );

    INSERT INTO users (user_id,  fname, lname) VALUES (1745, 'john', 'smith');
    SELECT * FROM users WHERE lname = 'smith';

All this does is create a simple users table and inserts some fake data into it. 
Let's save this CQL script into a file ``myscript.db``. Now you can run this example 
by typing:

.. code-block:: bash

    $ /service/bin/cqlsh -f myscript.db

Events and customization
------------------------

Connectors are customized using scripts that reside under ``/service/runscripts``. You should see a set of
directories, one for each type of ``event`` that Drydock produces. For example, the ``start`` directory contains
scripts that are executed when the connector is first started. Likewise, there are events for:

- ``start``: triggered when the connector is first started
- ``restart``: triggered when the connector is restarted
- ``stop``: triggered when the connector is stopped
- ``test``: triggered when the connector is asked to perform a test

You can add your own scripts to these directories, and they'll be executed in alphanumeric order. 

Saving everything
-----------------

Once you've installed all your packages and customized the ``runscripts``, you'll probably want to save your
progress. You can do this by typing:

.. code-block:: bash

   $ drydock snapshot sa-0
     sn-sa-0-81a67d8e-b75b-4919-9a65-50554d183b83

   $ drydock snapshots
                        UUID                      Base          Date
     -------------------------------------------- ------ --------------------
     sn-sa-4-81a67d8e-b75b-4919-9a65-50554d183b83 cassandra 02/5/2014 (02:02 PM)   

   $ drydock start sn-sa-0-81a67d8e-b75b-4919-9a65-50554d183b83
     sa-1

This will produce a ``snapshot`` that you can restart later. You can create as many snapshots as you want. 

*Note that due to some underlying issues with Docker, data saved outside the connector (i.e., in Cassandra) will not be saved across restarts.*

More resources
--------------

The Cassandra data model can take some getting used to. Once you do, you'll find that Cassandra
is relatively straightforward to use. Here are some additional resources that can help get you started. 

- `Apache Cassandra <http://cassandra.apache.org/>`_
- `DataStax Tutorial <http://www.datastax.com/resources/tutorials/>`_
- `myNoSQL Guide <http://nosql.mypopescu.com/post/573604395/tutorial-getting-started-with-cassandra/>`_
