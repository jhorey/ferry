:title: Ferry Introduction
:description: Introduction
:keywords: ferry, introduction

.. _intro:

Big Data Development Environment using Docker
=============================================

Ferry lets you share and deploy big data stacks on your local machine using Docker. Just define
your application like this:

.. code-block:: yaml

   backend:
      - storage:
           personality: "hadoop"
           instances: 2
           layers:
              - "hive"
   connectors:
      - personality: "hadoop-client"

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

Ferry currently supports Cassandra, Hadoop, GlusterFS, and Open MPI. Ferry can be used to:

- Experiment with big data technologies, such as Hadoop or Cassandra without having to learn the intricacies of configuring each software
- Share and evaluate other people's big data application quickly and safely via Dockerfiles
- Develop and test applications locally before being deployed onto an operational cluster
