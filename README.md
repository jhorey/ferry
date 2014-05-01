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
`docker` installed and type the following `pip install -U ferry`. More detailed installation instructions and examples can be found [here](http://ferry.opencore.io). 


Once installed, you can create your big data application using YAML files. 

```yaml
   backend:
      - storage:
           personality: "gluster"
           instances: 2
        compute:
           - personality: "yarn"
             instances: 2
   connectors:
      - personality: "hadoop-client"
        name: "control-0"
```

This stack consists of two GlusterFS data nodes, and two Hadoop/YARN compute nodes. There's also an Ubuntu-based
client that automatically connects to those backend components. Of course you can substitute your own
customized client. To create this stack, just type `ferry start yarn`. Once you create the stack, 
you can log in by typing `ferry ssh control-0`. 

Use cases
=========

Ferry is made for developers and data scientists that need something simple and powerful. It will help you: 

* Experiment with big data technologies, such as Hadoop or Cassandra without having to learn the intricacies of configuring each software
* Share and evaluate other people's big data application quickly and safely via Dockerfiles
* Develop and test applications locally before being deployed onto an operational cluster

Contributing
============

Contributions are totally welcome. Here are some suggestions on how to get started:

* Use Ferry, report bugs, and file new features! By filing issues and sharing your experience, you will help improve the software for others.
* Create Dockerfiles for your favorite backend, especially if you think the installation process is harder than it should be. The Dockerfile can be basic and we'll work together to get it ready for other users. 
* Create a new configuration module for your backend. This one is more complicated since it will involve actually hacking Ferry, but it's not so hard if we work together. 

I strongly recommend using GitHub issues + pull requests for contributions. Tweets sent to @open_core_io are also welcome. Happy hacking!

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
