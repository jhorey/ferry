Drydock: big data development engine
====================================

Drydock is an open source project to simplify the development of big data applications
on your local machine. 

Drydock lets you create Hadoop/Yarn, GlusterFS/OpenMPI, and Cassandra applications 
(with hopefully more in the future) without having to manually install or configure 
these services. It does this by leveraging [Docker](https://www.docker.io), a lightweight
Linux container deployment engine. Using Docker, we can more accurately replicate deployment 
environments, thus removing the headache of porting applications from development to operations. 

Big Data in small places
========================

Big data technologies are designed to operate and scale over many machines and usually consist
of multiple functional parts. While this is great from a scalability perspective, this is not
so great from an education and development perspective. Developers newly interested in creating a 
Hadoop application, for example, must first download the appropriate packages, configure these
systems to operate in a single-machine environment, and possibly configure other required
services (e.g., PostGresql). And this is just assuming a local environment!

Fortunately for us, Docker can be used to vastly simplify the packaging of all the necessary components.
All we have to do is tie all the pieces together and automate the configuration process. This enables
developers to quickly stand up a big data stack and attach connectors/clients with zero manual configuration. 
Because Docker is so lightweight, you can even test run multiple big data stacks with minimal overhead. 

Right now, we provide:

* Hadoop/Yarn
* Cassandra
* GlusterFS/OpenMPI

An example of a big data stack looks something like:
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

Getting started
===============

Drydock is a Python application and should be installed on your local machine. We provide an
installation script, but there are a few caveats:

* Your local machine should either have Docker installed or meet all Docker prerequisites
* You must have a functioning Python installation with pip installed

More detailed installation instructions can be found [here](http://opencore.io/drydock/gettingstarted). 

Usage examples
==============

Drydock can be used for experimenting with big data technologies, reproducing operational
environments, or for development of new big data applications. Because everything runs on
your local machine, it probably shouldn't be used for actual operations. 

You can find [examples](http://opencore.io/drydock/examples) in the documentation. 

Under the hood
==============

Drydock leverages some awesome open source projects:

* [Docker](https://www.docker.io) simplifies the management of Linux containers
* [Python](http://www.python.org) programming language
* [Hadoop](http://hadoop.apache.org) is a general-purpose big data storage and processing framework
* [GlusterFS](http://www.gluster.org) is a parallel filesystem actively developed by Redhat
* [OpenMPI](http://www.open-mpi.org) is a scalable MPI implementation focused on modeling & simulation
* [Cassandra](http://cassandra.apache.org) is a highly scalable column store
* [PostGresql](http://postgresql.org) is a popular relational database
