:title: Drydock Commands
:description: Drydock commands
:keywords: drydock, reference

------------
Command-Line
------------

Run ``drydock --help`` to get a list of available commands. 

daemon
------

Start the drydock daemon

.. code-block:: bash

    $ drydock daemon
    $ drydock -d

The drydock daemon controls all interaction with the actual
service and must be running to do anything. 

deploy
------

Deploy a service in an operational setting

.. code-block:: bash

    Usage: drydock deploy sn-fea3x --mode=local --conf=opconf
    
Deploying an application pushes your connector images to the cloud
and enables other users to interact with your application. Deployments
support multiple modes and configuration options. Use ``drydock deploy --help``
to view these options. 

*This feature is experimental*

help
----

Print out help information. Help for specific commands can be invoked
by typing ``drydock CMD --help``. 

info
----

Get the current ``drydock`` versioning information

This command lists all the running services.

inspect
-------

Print out detailed information about an application

For example:

.. code-block:: bash

    $ drydock inspect sa-0

This command prints out detailed information regarding the service, including
the list of all the docker containers that make up the service. Note that ``sa-0`` 
is the unique ID of a running service. 

install
-------

Build or rebuild all the necessary Docker images 

Images will be built with a custom public/private key pair
and will reside in a separate, local Docker repository.

logs
----

Copy over the logs to the host directory

For example:

.. code-block:: bash

    Usage: drydock logs sa-0 $LOGDIR
    
Note that ``sa-0`` is the unique ID of a running service, and ``LOGDIR`` is a directory 
on the host where the logs should be copied.

ps
--

List the available applications

By default this command will only print out ``running`` applications. You can
print out ``stopped`` and ``terminated`` applications by typing: ``drydock ps -a``. 

rm
--

Remove a stopped service 

For example: 
.. code-block:: bash

    $ drydock rm sa-0
    
Note that ``sa-0`` refers to a ``stopped`` application. Remove all data associated with the stack, 
including connector information. It is highly recommended to ``snapshot`` the state before removing an application. 
After removing the application, it may appear in the ``ps`` list for a short time. 

ssh
---

SSH into a running connector

For example: 

.. code-block:: bash

    $ drydock ssh sa-0 client-0

Note that `sa-0` refers to the unique service ID and `client-0` refers to the
user-defined connector name. If the connector name is not supplied, ``drydock``
will attempt to connect to the first available connector. 

start
-----

Start or restart an application

For example: 

.. code-block:: bash

    $ drydock start openmpi
    $ drydock start sa-0
    $ drydock start sn-aee3f...

The application may be new, a stopped application, or a snapshot. 

stop
----

Stop, but do not delete, a running application

For example: 

.. code-block:: bash

    $ drydock stop sa-0

    $ drydock ps
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

    $ drydock snapshot sa-0

Note that ``sa-0`` refers to either a ``running`` or ``stopped`` service. 
A snapshot saves all the connector state associated with a running service.
The user can create multiple snapshots. 

snapshots
---------

List all the available snapshots 

For example:

.. code-block:: bash

   $ drydock snapshots
                        UUID                      Base          Date
     -------------------------------------------- ------ --------------------
     sn-sa-4-81a67d8e-b75b-4919-9a65-50554d183b83 hadoop 02/5/2014 (02:02 PM)   
