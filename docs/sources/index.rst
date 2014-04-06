:title: Ferry Introduction
:description: Introduction
:keywords: ferry, introduction

.. _intro:

Big Data Development Environment using Docker
=============================================

Ferry lets you share and deploy big data applications on your local machine. Define your big data stack using YAML and
share your application with :ref:`Dockerfiles <advanced>`. Here's an example Hadoop cluster:

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
Hadoop cluster and a single Linux client. You can customize the Linux client during runtime or define your own using a Dockerfile. In addition to Hadoop, Ferry also supports Cassandra, GlusterFS, and Open MPI. 

Ferry is useful for:

- Data scientists that want to experiment and learn about big data technologies
- Developers that need a locally accessible big data development environment
- Users that want to share big data application quickly and safely

Ferry provides several useful commands for your applications: 

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

Ferry is under active development, so follow us on `Twitter <https://twitter.com/open_core_io/>`_ to keep up to date. 

If you're interested in collaborating or have any questions, feel free to send an email to `OpenCore <mailto://info@opencore.io/>`_. 
