:title: Open MPI example
:description: A simple example using GlusterFS and Open MPI
:keywords: ferry, example, glusterfs, openmpi

.. _mpi:

Getting started with Open MPI
============================

MPI is a popular parallel programming tool that abstracts various communication 
patterns and makes it relatively simple to coordinate code running across many 
machines. Unlike platforms such as Hadoop, MPI relies on a separate shared filesystem. 
In our case, we'll use GlusterFS, a distributed filesystem from Redhat. 

The first thing to do is define our stack in a file (let's call it ``openmpi.yaml``). 
The file should look something like this:

.. code-block:: yaml

   backend:
      - storage:
           personality: "gluster"
           instances: 2
        compute:
           - personality: "mpi"
             instances: 2
   connectors:
      - personality: "mpi-client"
        name: "control-0"

There are two main sections: the ``backend`` and ``connectors``. In this example, we're defining a single
``storage`` backend and a single ``compute`` backend. This backend is going to run two instances of ``gluster`` and
``mpi``. 

We'll also instantiate an MPI connector. The client will automatically mount the Gluster volume
and contain all the necessary configuration to launch new MPI jobs. By default the Gluster volume
is mounted under ``/service/data``. Of course you can remount the directory to wherever you like. Once
you've started your application and logged into your client, type ``mount`` to see the mount configuration. 

Note that we've assigned a ``name`` to our client (``control-0``). This is an *optional* user-defined value.
It helps if you have multiple clients and you want a simple way to ``ssh`` into a specific client. That capability
is illustrated in the next section. 

Running an example
------------------

Now that we've defined our stack, let's start it up. Just type the following in your terminal:

.. code-block:: bash

   $ ferry start openmpi
   sa-0

   $ ferry ps
   UUID Storage  Compute  Connectors  Status   Base  Time
   ---- ------- --------- ---------- ------- ------- ----
   sa-0    se-0 [u'se-1']       se-2 running openmpi   --

The entire process should take about 20 seconds. Before we continue, let's take a step back to 
examine what just happened. After typing ``start``, ``ferry`` created the following Docker
containers:

- Two Gluster data nodes (sometimes called a "brick")
- Two Open MPI compute nodes
- A Linux client

Now that the environment is created, let's interact with it by connecting to the Linux client. 
Just type ``docker ssh sa-0`` in your terminal. By default, the ``ssh`` command will log you
into the first client. If you have multiple clients and you've assigned them names, you can
specify the client by typing ``docker ssh sa-0 control-0`` (where ``control-0`` is the name
you've defined for that client). 

Once you're logged in, let's check what environment variables have been created. Remember
this is all being run from the connector. 

.. code-block:: bash

   $ env | grep BACKEND
   BACKEND_STORAGE_TYPE=gluster
   BACKEND_STORAGE_IP=10.1.0.3
   BACKEND_COMPUTE_TYPE=openmpi
   BACKEND_COMPUTE_IP=10.1.0.5

Notice there are two sets of environment variables, once for the storage and the other for the compute. 

Now if you're really impatient to get an Open MPI application working, just type the following into
the terminal:

.. code-block:: bash

   $ /service/runscripts/test/test01.sh

It will take a few seconds to complete, but you should see some output that comes from
executing the application. If you want to know what you just did, take a peek at the
``/service/runscripts/test/test01.sh`` file. 

Ok, now let's actually compile some code and run it. Here's a super simple ``hello world`` example:

.. code-block:: c++

    #include <mpi.h>

    int main(int argc, char **argv)
    {
        int numprocs, rank, namelen;

        MPI_Init(&argc, &argv);
        MPI_Comm_size(MPI_COMM_WORLD, &numprocs);
        MPI_Comm_rank(MPI_COMM_WORLD, &rank);

	if(rank == 0) {
	    std::cout << "master (" << rank << "/" << numprocs << ")\n";
        }
	else {
            std::cout << "slave (" << rank << "/" << numprocs << ")\n";
	}

        MPI_Finalize();
     }

All it does is initialize MPI, determine who the masters & slaves are, and prints
out some information to the console. We can compile and run this example by typing the following in a terminal:

.. code-block:: bash

    $ su ferry 
    $ mpic++ -W -Wall /service/examples/helloworld.cpp -o /service/data/binaries/helloworld.o
    $ mpirun -np 4 --hostfile /usr/local/etc/instances /service/data/binaries/helloworld.o

Note that the we must pass in the ``instances`` file to ``mpirun``. This file contains the set
of Open MPI hosts that can execute the code. 

Although this example does not read or write to shared storage, everything under ``/service/data`` 
is shared across all the Open MPI nodes and the Linux client. 

A YARN example
--------------

In addition to Open MPI, you can also create a YARN compute cluster that uses GlusterFS for storage. 
YARN is the next-generation Hadoop compute layer that enables more flexibility compared to
the old MapReduce API. The configuration file will look something like this:

.. code-block:: javascript

    {
      "backend":[
       {
        "storage":
            {
  	       "personality":"gluster",
  	       "instances":2
	    },
        "compute":[
	    {
	      "personality":"yarn",
	      "instances":2
	    },]
       }],
      "connectors":[
	    {"personality":"hadoop-client"}
      ]
    }

Note that under ``compute``, we've replaced the ``mpi`` section with a ``yarn`` section. After starting this
stack, you should be able to run normal Hadoop and Hive applications. You can find some examples under
``/service/runscripts/test``.

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
     -------------------------------------------- ------- --------------------
     sn-sa-4-81a67d8e-b75b-4919-9a65-50554d183b83 openmpi 02/5/2014 (02:02 PM)   

   $ ferry start sn-sa-0-81a67d8e-b75b-4919-9a65-50554d183b83
     sa-1

This will produce a ``snapshot`` that you can restart later. You can create as many snapshots as you want. 

*Note that due to some underlying issues with Docker, data saved outside the connector (i.e., in Gluster) will not be saved across restarts.*

More resources
--------------

MPI is relatively complex compared to other more recent frameworks such as Hadoop, but is very useful for
applications that require complex coordination. Here are some additional resources you can use to learn
more. 

- `Open MPI <http://www.open-mpi.org/>`_
- `Using MPI Examples <http://www.mcs.anl.gov/research/projects/mpi/usingmpi/>`_
- `MPI Scientific Computing <http://www.mcs.anl.gov/research/projects/mpi/tutorials/mpibasics/index.htm/>`_
- `Apache Hadoop YARN <http://hortonworks.com/blog/introducing-apache-hadoop-yarn/>`_
