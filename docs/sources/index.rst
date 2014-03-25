:title: Ferry Introduction
:description: Introduction
:keywords: ferry, introduction

.. _intro:

Big Data Development Environment using Docker
=============================================

Ferry lets you provision and deploy big data stacks on your local machine using Docker. Just define
your application like this:

.. code-block:: javascript

   {
     "backend":[
      {
       "storage":
           {
  	      "personality":"hadoop",
  	      "instances":2,
  	      "layers":["hive"]
	   }
      }], 
      "connectors":[
	   {"personality":"hadoop-client"}
     ]
   }

Then get started by typing ``ferry start hadoop``. This will automatically create a two node
Hadoop cluster and a single Linux client. There are commands to:

- Start and stop services
- View status and create snapshots
- SSH into clients
- Copy over log files to a host directory

For example, let's inspect all the running services

.. code-block:: bash

   $ ferry ps
   UUID Storage  Compute  Connectors  Status   Base  Time
   ---- ------- --------- ---------- ------- ------- ----
   sa-2    se-6 [u'se-7']       se-8 removed hadoop    --
   sa-1    se-3 [u'se-4']       se-5 stopped openmpi   --
   sa-0    se-0 [u'se-1']       se-2 running cassandra --

Ferry currently supports Cassandra, Hadoop, and Gluster/OpenMPI. Use cases include:

- Experimenting with big data technologies like Hadoop and Cassandra
- Prototyping big data stacks on a single machine
- Mirroring an operational environment on development machines
