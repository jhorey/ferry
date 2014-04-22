:title: Hadoop example
:description: A simple example using Hadoop
:keywords: ferry, example, hadoop

.. _hadoop:

Getting started with Hadoop
===========================

Hadoop is a popular big data platform that includes both storage (HDFS) and compute (YARN). 
In this example, we'll create a small 2 node Hadoop cluster, and a single Linux client. 
		
The first thing to do is to define our big data stack. You can either use YAML or JSON. Let's call our new application stack ``hadoop.yaml``. 
The file should look something like this:

.. code-block:: yaml

   backend:
      - storage:
           personality: "hadoop"
           instances: 2
           layers:
              - "hive"
   connectors:
      - personality: "hadoop-client"

There are two main sections: the ``backend`` and ``connectors``. In this example, we're defining a single
``storage`` backend. This ``storage`` backend is going to run two instances of ``hadoop`` and also installs
``hive``, an SQL compatability layer for Hadoop. The ``backend`` may also optionally include a ``compute``
section (for example additional ``yarn`` instances). However, in this example, we won't need one since 
Hadoop will automatically come with its own compute capabilities. 

Connectors are basically Linux clients that are able to connect to the backend. You'll want at least one to simplify
interacting with Hadoop. You can also place your application-specific code in the connector (for example, your web server). In this example, we'll
use the built-in ``hadoop-client``.

Running an example
------------------

Now that we've defined our stack, let's start it up. Don't forget that you need the Ferry server to be up and running (via ``sudo ferry server``). Afterwards type the following in your terminal:

.. code-block:: bash

   $ ferry start hadoop
   sa-0

   $ ferry ps
   UUID Storage  Compute  Connectors  Status   Base  Time
   ---- ------- --------- ---------- ------- ------- ----
   sa-0    se-0 [u'se-1']       se-2 running hadoop    --

``hadoop`` should be replaced with the path to your specific file. Otherwise it will use a default Hadoop
stack. The entire process should take less than a minute. 

Before we continue, let's take a step back to examine what just happened. After typing ``start``, ``ferry`` created the following Docker
containers:

- Two Hadoop data/yarn nodes
- Hadoop namenode
- Hadoop YARN resource manager
- A Hive metadata server
- A Linux client

For those that already run ``docker`` for other reasons, don't worry, ``ferry`` uses a 
separate Docker daemon so that you're environment is left unaffected. 

Now that the environment is created, let's interact with it by connecting to the Linux client. 
Just type ``ferry ssh sa-0`` in your terminal. From there you'll can check your backend connection 
and install whatever you need. 

Now let's check what environment variables have been created. Remember
this is all being run from the connector. 

.. code-block:: bash

   $ env | grep BACKEND
   BACKEND_STORAGE_TYPE=hadoop
   BACKEND_STORAGE_IP=10.1.0.3

Now if you're really impatient to get a Hadoop application working, just type the following into
the terminal:

.. code-block:: bash

   $ /service/runscripts/test/test01.sh hive

It will take a minute or two to complete, but you should see a bunch of output that comes from
executing the application. If you want to know what you just did, take a peek at the
``/service/runscripts/test/test01.sh`` file. 

Now let's manually run some Hadoop jobs to confirm that everything is working. We're going 
download a dataset from internet. It's very important that we run everything as the
``ferry`` user (as opposed to ``root``). Otherwise you may see strange errors associated with
permissions. So switch over to the ``ferry`` user by typing: 

.. code-block:: bash

    $ su ferry
    $ source /etc/profile

That last command just sets the ``PATH`` environment variable so that you can find the
``hadoop`` and ``hive`` commands. To confirm, if you type the following, you should see
the full path of the ``hive`` command. Of course, you can also just type in the full path
if you prefer. 

.. code-block:: bash

    $ which hive
    /service/packages/hive/bin/hive

Now that the ``PATH`` is set, we're going to copy that dataset into the Hadoop filesystem. 
This is a necessary pre-condition to actually running any Hadoop jobs that operate over the data. 

.. code-block:: bash

    $ wget http://files.grouplens.org/datasets/movielens/ml-100k/u.data -P /tmp/movielens/
    $ hdfs dfs -mkdir -p /data/movielens
    $ hdfs dfs -copyFromLocal /tmp/movielens/u.data /data/movielens

Now we're going to create the Hive tables. This will let us use ``SQL`` to interact
with the data. To save our progress, let's create a file ``createtable.sql`` to store
all of our SQL. The file should contain something like this:

.. code-block:: bash

   CREATE TABLE  movielens_users (
	userid INT,
	movieid INT,
	rating INT,
	unixtime STRING
   ) 
   ROW FORMAT DELIMITED
   FIELDS TERMINATED BY '\t'
   STORED AS TEXTFILE;

   LOAD DATA INPATH '/data/movielens/u.data'
   OVERWRITE INTO TABLE movielens_users;

Hive lets you create tables using different formats. Here we're using the "Textfile"
format to initially load the data. Afterwards, you can load the data into alternative 
formats such as "RCfile" for better performance. 

After creating our SQL file, we can execute the query by typing: 

.. code-block:: bash

    $ hive -f createtable.sql

This should execute several MapReduce jobs (you'll see a bunch of output to the screen).
After it's done loading, we can query this table. Let's do this interactively: 

.. code-block:: bash

    $ hive
    $ hive> SELECT COUNT(userid) FROM movielens_users WHERE userid < 10;
    ...
    Job 0: Map: 1  Reduce: 1   Cumulative CPU: 4.55 sec   HDFS Read: 387448 HDFS Write: 5 SUCCESS
    Total MapReduce CPU Time Spent: 4 seconds 550 msec
    OK
    1282

You'll see way more output, but the last few lines should like this. 

Compiling a new application
---------------------------

Running a custom MapReduce program is pretty straightforward. First we compile, then we package the
results in a jar file, and then invoke the ``hadoop`` command. Here's an example: 

.. code-block:: bash

    $ javac -classpath $HADOOP_HOME -d Wordcount/ Wordcount.java
    $ jar -cvf Wordcount.jar -C Wordcount/ .
    $ hadoop jar Wordcount.jar org.opencore.Wordcount test/ testout/

If you want to find a copy of the ``Wordcount.java`` file, look in the file ``hadoop-mapreduce-examples-2.2.0-sources.jar``. 
``jar`` files are just zip files, so you can use unzip it and find what you need. 

Events and customization
------------------------

Each connector is a complete Linux (Ubuntu) environment that can be completely configured. In fact, the connector is just
a normal Docker container with a few extra scripts and packages pre-configured. That means you can install additional packages
or include new code. Afterwards, it's easy to save the entire state. 

Connectors are customized using scripts that reside under ``/service/runscripts``. You should see a set of
directories, one for each type of ``event`` that Ferry produces. For example, the ``start`` directory contains
scripts that are executed when the connector is first started. Likewise, there are events for:

- ``start``: triggered when the connector is first started
- ``restart``: triggered when the connector is restarted
- ``stop``: triggered when the connector is stopped
- ``test``: triggered when the connector is asked to perform a test

If you look in the ``test`` directory, you'll find some example programs that you can execute. 
You can add your own scripts to these directories, and they'll be executed in alphanumeric order. 

Saving everything
-----------------

Once you've installed all your packages and customized the ``runscripts``, you'll probably want to save your
progress. You can do this by typing:

.. code-block:: bash

   $ ferry snapshot sa-0
     sn-sa-0-81a67d8e-b75b-4919-9a65-50554d183b83

   $ ferry snapshots
                        UUID                      Base          Date
     -------------------------------------------- ------ --------------------
     sn-sa-4-81a67d8e-b75b-4919-9a65-50554d183b83 hadoop 02/5/2014 (02:02 PM)   

   $ ferry start sn-sa-0-81a67d8e-b75b-4919-9a65-50554d183b83
     sa-1

This will produce a ``snapshot`` that you can restart later. You can create as many snapshots as you want. 

More resources
--------------

Most of these examples can also be found in the ``hadoop-client`` connector. Just navigate to ``/service/runscripts/test``
and you'll find a couple scripts that basically do what we just documented. 

Hadoop is fairly complicated with many moving pieces and libraries. Hopefully ``ferry`` will make it easier
for you to get started. Once you're comfortable with these examples, here are some additional resources to 
learn more. 

- `Apache Hadoop <http://hadoop.apache.org/>`_
- `Yahoo Developers <http://developer.yahoo.com/hadoop/tutorial/>`_
- `Cloudera Tutorial <https://www.cloudera.com/content/cloudera-content/cloudera-docs/HadoopTutorial/CDH4/Hadoop-Tutorial.html/>`_
