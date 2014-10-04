:title: Ferry on AWS
:description: Running Ferry on AWS
:keywords: ferry, installation, aws

.. _aws:

Amazon Web Services
===================

Ferry comes with built-in support for AWS, and lets you launch, run, and manage
big data clusters on Amazon EC2. This means that you can quickly spin up a new
Hadoop, Spark, Cassandra, or Open MPI cluster on AWS with just a few simple commands. 

Ferry on AWS offers several advantages over tools such as Elastic MapReduce. 

1. Greater control over storage. You can instruct Ferry to use either ephemeral or elastic block storage.
2. Greater control over the network. You can launch instances in either a public or private subnet (via VPC). 
3. Ability to mix-and-match components such as Oozie and Hue.
4. Ability to manage multiple clusters of different types (Hadoop, Spark, and Cassandra all from a single control interface).

Before You Start
----------------

This documentation assumes that you have access to an Amazon Web Services account. If you don't, go ahead and create 
one `now <http://aws.amazon.com/ec2/>`_. You'll also probably want to create a new key pair for Ferry. While you can use
an existing key pair, that is considered poor practice. 

Ferry launches new instances into private subnets within a VPC. While more secure than legacy EC2, it does mean
that you'll need to have a VPC set up for Ferry to use. Most likely your AWS account already has this set up. If
not, just navigate to Services -> VPC on your AWS homepage. Click on the "Your VPCs" menu to browse available VPCs.
If do you have a VPC set up, you'll want to remember the "VPC ID" (we'll use it during the configuration stage). 

Otherwise, if you don't have any VPCs set up, just click on "Create VPC". Amazon doesn't charge you for creating a 
VPC, so don't be afraid of messing up. After your VPC is set up, just note the "VPC ID". For those that need more
help, here's a friendly [VPC tutorial](http://docs.aws.amazon.com/AmazonVPC/latest/GettingStartedGuide/Wizard.html). 

Once the VPC is set up, Ferry will automatically handle the creation of the various subnets (unless you provide your
own subnet information). 

In summary, you will need:

1. An active Amazon Web Services account
2. A keypair used for communicating with Ferry EC2 instances
3. A working VPC

Launch Summary
--------------

1. Create new Ferry client VM
2. Create a new Ferry configuration file
3. Start the Ferry server as root via `sudo ferry server`
4. Launch new clusters via `sudo ferry start hadoop`

Launching
---------

The very first step is to have a functioning `Ferry <http://ferry.opencore.io/>`_ installation. 
The quickest way to get a functioning Ferry installation is to use our public client image. Search for "Ferry"
under "Community Images". The image is currently available in the US East and US West (N. California) regions. 

Please note that for the AWS backend to work properly, the client has to be running in the *same* VPC that the Ferry instances  will be running. 
Otherwise, the client won't be able to communicate with your instances when they're launched in a private subnet. 

After spinning up the client VM, ssh into it:

.. code-block:: bash

    $ ssh -i MY_AWS_KEY.pem ubuntu@MY_IP_ADDRESS

Please note that as of right now, Ferry requires root accesss, type the following:

.. code-block:: bash

    $ sudo su
    $ export FERRY_DIR=/ferry/master

That last command tells Ferry where to find all the Ferry images. If you're using your own
client installation (instead of our AWS image), you can probably skip that part. 

Now it's time to create the configuration file. 

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
        image: ami-486ad920
        personality: $EC2_TYPE
        vpc: $VPC_ID
        manage_subnet: $SUBNET_ID
        data_subnet: $SUBNET_ID
        default-user: ubuntu
        ssh: $EC2_KEYPAIR
        ssh-user: ferry
        public: false
        user: $API USER
        access: $API_ACCESS
        secret: $API_SECRETY

The most important parameters are:

* $EC2_TYPE: This is the instance type for all the VMs created by Ferry. The minimum size supported is `t2.small`, although
you'll want something larger for production environments
* $EC2_KEYPAIR: This is the key pair that Ferry will use to communicate with the VMs. You *must* place the private in 
`/ferry/keys/` so that Ferry can find it. 
* $API_USER: Your EC2 user handle. 
* $API_ACCESS: Your EC2 access token. You can find these credentials from the AWS homepage by clicking Account, Security Credentials,
Access Credentials.
* $API_SECRET: Your EC2 secret key. You can find these credentials from the AWS homepage by clicking Account, Security Credentials,
Access Credentials.

Storage
-------

You can specify the storage capabilities of the VMs via the `volume` parameter. 
The syntax for modifying this parameter is:

* [ebs,ephemeral]:(size)

For example, to use 32GB EBS data volumes, set the value to: `ebs:32`. To use
the instance store, just set the value to `ephemeral`. You can't specify the
ephemeral block size since that is determined by your instance type. 

Networking
----------

You can specify the networking configuration via the following parameters:

* vpc: (Mandatory) Replace this with your VPC ID. 
* manage_subnet: (Optional) If you specify a subnet ID, connectors will be launched into
that subnet. Otherwise a new public subnet will be created. 
* data_subnet: (Optional) If you specify a subnet ID, backend nodes will be launched into
that subnet. Otherwise a new data subnet will be created. 
* public: (Optional) If set to `true`, then the data subnet will be public. Otherwise, the
data subnet will be private. The default value is `false`. 

Region and AMI
--------------

Finally, you can specify the EC2 region via the following parameters:

* dc: The EC2 region to use. 
* zone: The availability zone to use.

Depending on which EC2 region you specify, you'll need to change the AMI. 

+------------+----------------+
| Region     | AMI            |
+============+================+
| us-east-1  | ami-486ad920   |
+------------+----------------+
| us-west-1  | ami-c7888382   |
+------------+----------------+

Please note that only `us-east-1` and `us-west-1` are officially supported. 
Please file a `GitHub issue <https://github.com/opencore/ferry/issues/>`_ for additional region support.

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

Terminating the Cluster
-----------------------

If you want to stop your cluster, just type:

.. code-block:: bash

    $ sudo ferry stop sa-bfa98eda

You can restart the same cluster by typing:

.. code-block:: bash

    $ sudo ferry start sa-bfa98eda

Once you're finished, you can delete the entire cluster by typing:

.. code-block:: bash

    $ sudo ferry rm sa-bfa98eda

This will remove all the resources associated with the cluster. *Be warned, however, that
doing so will delete all the data associated with the cluster!*. 

Future Features
---------------

There are a few features that aren't quite implemented yet. 

1. Spot instance support. All instances are currently allocated in an on-demand manner. 
2. Heterogeneous instance types. At the moment, all instances use the same instance type. 
3. Resizing clusters. Once a cluster is created, the size of the cluster is fixed. 

If any of these features are particularly important to you, please consider `contributing <https://github.com/opencore/ferry/>`_. 
