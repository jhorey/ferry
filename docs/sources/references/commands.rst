:title: Ferry Commands
:description: Ferry commands
:keywords: ferry, reference

------------
Command-Line
------------

Run ``ferry --help`` to get a list of available commands. 

deploy
------

Deploy a service in an operational setting

.. code-block:: bash

    $ ferry deploy sn-fea3x --mode=local --conf=opconf
    
Deploying an application pushes your connector images to the cloud
and enables other users to interact with your application. Deployments
support multiple modes and configuration options. Use ``ferry deploy --help``
to view these options. 

*This feature is experimental*

help
----

Print out help information. Help for specific commands can be invoked
by typing ``ferry CMD --help``. 

info
----

Get the current ``ferry`` versioning information

This command lists all the running services.

inspect
-------

Print out detailed information about an application (either running or installed)

For example:

.. code-block:: bash

    $ ferry inspect sa-0

This command prints out detailed information regarding the service, including
the list of all the docker containers that make up the service. Note that ``sa-0`` 
is the unique ID of a running service. 

install
-------

Build or rebuild all the necessary Docker images 

For example:

.. code-block:: bash

    $ sudo ferry install -k $MY_KEY_DIRECTORY

Images can be built with a custom public/private key pair by specifying the ``-k`` parameter. 

logs
----

Copy over the logs to the host directory

For example:

.. code-block:: bash

    Usage: ferry logs sa-0 $LOGDIR
    
Note that ``sa-0`` is the unique ID of a running service, and ``LOGDIR`` is a directory 
on the host where the logs should be copied.

ls
--

List installed applications

.. code-block:: bash

    $ ferry ls
       App           Author       Version           Description
       ---           ------       -------           -----------
    cassandra     James Horey      0.2.0         Cassandra stack...
      hadoop      James Horey      0.2.0          Hadoop stack...
     openmpi      James Horey      0.2.0      Open MPI over Gluster...
      spark       James Horey      0.2.0        Spark over Hadoop...
       yarn       James Horey      0.2.0      Hadoop YARN over Glus...

ps
--

List the available applications

By default this command will only print out ``running`` applications. You can
print out ``stopped`` and ``terminated`` applications by typing: ``ferry ps -a``. 

pull
----

Download either individual Docker images or complete Ferry applications

For example: 

.. code-block:: bash

    $ ferry pull app://<user>/<app>
    $ ferry pull image://<user>/<image>

If you download an application, all the necessary images will download automatically. 

push
----

Upload either individual Docker images or complete Ferry applications

For example: 

.. code-block:: bash

    $ ferry push app:///home/ferry/myapp.yml
    $ ferry push image://<user>/<image>

If you upload an application, all the necessary images will be uploaded automatically to the Docker registry
specified in the Ferry authorization file. 

rm
--

Remove a stopped service 

For example: 

.. code-block:: bash

    $ ferry rm sa-0
    
Note that ``sa-0`` refers to a ``stopped`` application. Remove all data associated with the stack, 
including connector information. It is highly recommended to ``snapshot`` the state before removing an application. 
After removing the application, it may appear in the ``ps`` list for a short time. 

server
------

Start the ferry daemon

.. code-block:: bash

    $ sudo ferry server

The ferry server controls all interaction with the actual
service and must be running to do anything. 

ssh
---

SSH into a running connector

For example: 

.. code-block:: bash

    $ ferry ssh sa-0 client-0

Note that `sa-0` refers to the unique service ID and `client-0` refers to the
user-defined connector name. If the connector name is not supplied, ``ferry``
will attempt to connect to the first available connector. 

start
-----

Start or restart an application

For example: 

.. code-block:: bash

    $ ferry start openmpi
    $ ferry start sa-0
    $ ferry start sn-aee3f...

The application may be new, a stopped application, or a snapshot. 

stop
----

Stop, but do not delete, a running application

For example: 

.. code-block:: bash

    $ ferry stop sa-0

    $ ferry ps
    UUID Storage  Compute  Connectors  Status   Base  Time
    ---- ------- --------- ---------- ------- ------- ----
    sa-0    se-0 [u'se-1']       se-2 stopped hadoop    --    
    
Note that ``sa-0`` is the unique ID of the running service. After the
service is stopped, the service can be restarted. All state in the connectors
are preserved across start/restart events. 

snapshot
--------

Take a snapshot of an application

For example:

.. code-block:: bash

    $ ferry snapshot sa-0

Note that ``sa-0`` refers to either a ``running`` or ``stopped`` service. 
A snapshot saves all the connector state associated with a running service.
The user can create multiple snapshots. 

snapshots
---------

List all the available snapshots 

For example:

.. code-block:: bash

   $ ferry snapshots
                        UUID                      Base          Date
     -------------------------------------------- ------ --------------------
     sn-sa-4-81a67d8e-b75b-4919-9a65-50554d183b83 hadoop 02/5/2014 (02:02 PM)   

quit
----

Stop the Ferry servers

This will gracefully shutdown the servers controlling Ferry. This command
must be executed via ``sudo``. 
