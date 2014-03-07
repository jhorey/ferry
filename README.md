Ferry: big data development engine
====================================

Ferry lets you define, run, and deploy big data stacks on your local machine using [Docker](https://www.docker.io).

Ferry currently supports Hadoop/Yarn, GlusterFS/OpenMPI, and Cassandra (with more in the future). 
By using Ferry developers can get started creating their big data applications right away without
the pain of installing and configuring all the complex backend software.

Big Data in small places
========================

Big data technologies are designed to operate and scale over many machines and usually consist
of multiple functional parts. Developers interested in creating a 
Hadoop application, for example, must first download the appropriate packages, configure these
systems to operate in a single-machine environment (or multiple machines for operational environments), 
and configure other required services (e.g., PostGresql). 

Fortunately for us, Ferry and Docker vastly simplifies the entire process by capturing the entire process
in a set of lightweight Linux containers. This enables developers to quickly stand up a big data stack and 
attach connectors/clients with zero manual configuration. Because Docker is so lightweight, you can even test 
multiple big data stacks with minimal overhead. 

Getting started
===============

Ferry is a Python application and runs on your local machine. All you have to do to get started is have
`docker` installed and type the following `pip install -U ferry`. Afterwards you can start creating
your big data application. Here's an example stack:

```javascript
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
	  "personality":"mpi",
	  "instances":2
	}]
   }],
  "connectors":[
	{"personality":"mpi-client"}
  ]
}
```

This stack consists of two GlusterFS data nodes, and two OpenMPI compute nodes. There's also a Linux
client that automatically connect to those backend components. To create this stack, just type
`ferry start openmpi`. Once you create the stack, you can log in by typing `ferry ssh sa-0`. 

More detailed installation instructions and examples can be found [here](http://ferry.opencore.io). 

Under the hood
==============

Ferry leverages some awesome open source projects:

* [Docker](https://www.docker.io) simplifies the management of Linux containers
* [Python](http://www.python.org) programming language
* [Hadoop](http://hadoop.apache.org) is a general-purpose big data storage and processing framework
* [GlusterFS](http://www.gluster.org) is a parallel filesystem actively developed by Redhat
* [OpenMPI](http://www.open-mpi.org) is a scalable MPI implementation focused on modeling & simulation
* [Cassandra](http://cassandra.apache.org) is a highly scalable column store
* [PostGresql](http://postgresql.org) is a popular relational database
