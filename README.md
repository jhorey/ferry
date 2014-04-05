Ferry: Big Data Development Environment using Docker
====================================================

Ferry lets you share and deploy big data applications on your local machine using [Docker](https://www.docker.io).

First create and package your Hadoop/Yarn, GlusterFS/OpenMPI, or Cassandra application in a Dockerfile. 
Then deploy your application without the pain of installing and configuring all the complex backend software.

Big data technologies are designed to scale over many machines and are complex to install and set up. 
Fortunately for us, Ferry simplifies the entire process by capturing the entire process
in a set of lightweight Linux containers. This enables developers to quickly stand up a big data stack and 
develop applications with zero manual configuration. Because Ferry uses Docker, developers can then share
their Dockerfiles for others to use. 

Getting started
===============

Ferry is a Python application and runs on your local machine. All you have to do to get started is have
`docker` installed and type the following `pip install -U ferry`. Afterwards you can start creating
your big data application. Here's an example stack:

```yaml
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
```

This stack consists of two GlusterFS data nodes, and two Open MPI compute nodes. There's also an MPI
client that automatically connects to those backend components. Of course you can substitute your own
customized client. To create this stack, just type `ferry start openmpi`. Once you create the stack, 
you can log in by typing `ferry ssh control-0`. 

More detailed installation instructions and examples can be found [here](http://ferry.opencore.io). 

Use cases
=========

Ferry can be used to:

* Experiment with big data technologies, such as Hadoop or Cassandra without having to learn the intricacies of configuring each software
* Share and evaluate other people's big data application quickly and safely via Dockerfiles
* Develop and test applications locally before being deployed onto an operational cluster

Under the hood
==============

Ferry leverages some awesome open source projects:

* [Docker](https://www.docker.io) simplifies the management of Linux containers
* [Python](http://www.python.org) programming language
* [Hadoop](http://hadoop.apache.org) is a general-purpose big data storage and processing framework
* [GlusterFS](http://www.gluster.org) is a parallel filesystem actively developed by Redhat
* [OpenMPI](http://www.open-mpi.org) is a scalable MPI implementation focused on modeling & simulation
* [Cassandra](http://cassandra.apache.org) is a highly scalable column store
* [PostgreSQL](http://postgresql.org) is a popular relational database
