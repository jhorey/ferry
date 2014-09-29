:title: Ferry on AWS
:description: Running Ferry on AWS
:keywords: ferry, installation, aws

.. _aws:

Amazon Web Services
===================

Ferry comes with built-in support for AWS, and lets you launch, run, and manage
big data clusters on Amazon EC2. This means that you can quickly spin up a new
Hadoop, Spark, Cassandra, or Open MPI cluster with just a few simple commands. 

Ferry on AWS offers several advantages over tools such as Elastic MapReduce. 

1. Greater control over storage. You can instruct Ferry to use either ephemeral or elastic block storage.
2. Greater control over the network. You can launch instances in either a public or private subnet (via VPC). 
3. Ability to mix-and-match components such as Oozie and Hue.
4. Ability to manage multiple clusters of different types (Hadoop, Spark, and Cassandra all from a single control interface).

Before You Start
----------------

This documentation assumes that you have access to an Amazon Web Services account. If you don't, go ahead and create 
one [now](http://aws.amazon.com/ec2/). You'll also probably want to create a new key pair for Ferry. While you can use
an existing key pair, that is considered poor practice. 

In summary, you will need:

1. An active Amazon Web Services account
2. A keypair used for communicating with Ferry EC2 instances

Launch Summary
--------------

1. Create new Ferry client VM using the "Ferry Server (small)" image
2. Create a new Ferry configuration file
3. Start the Ferry server as root via `sudo ferry server`
4. Launch new clusters via `sudo ferry start hadoop`

Launching
---------


Configuration
-------------

In order to tell Ferry to use the AWS backend, you'll need to create a Ferry
configuration file. 

Create a new configuration file `~/.ferry-config.yaml`. If you have a pre-existing
configuration, you can just modify that one instead. 

You want your configuration to look like this: 

.. code-block:: yaml

    system:
      provider: aws
      backend: ferry.fabric.cloud/CloudFabric
      mode: ferry.fabric.aws.awslauncher/AWSLauncher
      proxy: false
    web:
      workers: 1
      bind: 0.0.0.0
      port: 4000
    aws:
      params:
        dc: us-east-1
        zone: us-east-1b
        volume: ebs:8
      deploy:
         image: ami-xxxyyy
         personality: t2.micro
         default-user: ubuntu
         ssh: ferry-aws
         ssh-user: ferry
         public: false
         user: APIUSER
         access: APIACCESSKEY
         secret: APISECRETKEY

Running Examples
----------------

After you've created your configuration file, you should start the Ferry server:

.. code-block:: bash

    $ sudo ferry server

It'll take a few seconds, but you'll eventually see output that indicates that you're using the AWS
backend. 

.. code-block:: bash

    $ sudo ferry server
    ...
    using heat server http://10.1.0.3:8004/v1/42396664178112
    using backend cloud ver:0.1

Afterwards, you should be able to start a new application stack. 

.. code-block:: bash

    $ sudo ferry start hadoop

Starting the Hadoop stack can take 10 minutes or longer. If you login to your AWS CloudFormation interface, 
you should be able to see the VMs being instantiated. You can also check the status via Ferry:

.. code-block:: bash

    $ sudo ferry ps
      UUID            Storage          Compute        Connectors         Status         Base       Time
      ----            -------          -------        ----------         ------         ----       ----
   sa-bfa98eda            []             [' ']             []            building       hadoop

    $ sudo ferry ps
      UUID            Storage          Compute        Connectors         Status         Base       Time
      ----            -------          -------        ----------         ------         ----       ----
   sa-bfa98eda     [u'se-60c89300']      [' ']      [u'se-0b841c69']     running        hadoop

Once the stack is in the `running` state, log in to the Hadoop client:

.. code-block:: bash

    $ sudo ferry ssh sa-bfa98eda

Afterwards, run a simple Hadoop job:

.. code-block:: bash

    $ /service/runscripts/test/test01.sh hive

That's it! Once you're done, you can stop and delete the entire Hadoop cluster:

.. code-block:: bash

    $ sudo ferry stop sa-bfa98eda
    $ sudo ferry rm sa-bfa98eda

Future Features
---------------

There are a few features that aren't quite implemented yet (please consider [contributing](https://github.com/opencore/ferry)). 

1. Spot instance support. All instances are currently allocated in an on-demand manner. 
2. Heterogeneous instance types. At the moment, all instances use the same instance type. 
3. Resizing clusters. Once a cluster is created, the size of the cluster is fixed. 

If any of these features are particularly important to you, please submit an [issue](https://github.com/opencore/ferry/issues). 
