:title: Multiple storage and compute
:description: How to push and pull new applications
:keywords: ferry, example 

.. _multiple:

Multiple Storage and Compute
============================

Although many application consist of a single storage layer, you can actually combine
multiple storage layers. This lets you construct complex applications that uses the
storage in different ways. For example, here we're using both Hadoop (HDFS) and
MongoDB, a popular document store.  

.. code-block:: yaml

    backend:
       - storage:
            personality: "hadoop"
            instances: ">=1"
            layers:
               - "hive"
       - storage:
            personality: "mongodb"
            instances: 1
    connectors:
       - personality: "ferry/hadoop-client"

Hadoop is great at storing the archival data for analytic purposes, while MongoDB
may be used for transactional data. Once you're logged into the client, you'll find
environment variables that refer to both sets of storage. 

*One word of warning: the bult-in client for Hadoop doesn't have MongoDB drivers installed, so you'll want to install that before anything else*. 

You can also combine multiple compute layers. For example, we might create a *data science* application that uses both Hadoop/YARN and OpenMPI. 

.. code-block:: yaml

    backend:
       - storage:
            personality: "gluster"
            instances: 1
         compute:
            - personality: "yarn"
              instances: 1
              layers: 
                 - "hive"
            - personality: "openmpi"
              instances: 1
    connectors:
       - personality: "ferry-user/data-science"

In this example, we're supplying our own custom client that has both YARN and Open MPI drivers installed. 
