:title: Ferry on OpenStack
:description: Running Ferry on an OpenStack Cloud
:keywords: ferry, installation, openstack

.. _osclient:

OpenStack
=========

This documentation is meant for Ferry end users.  Before we can get started, 
however, the Ferry server image will need to be installed in the OpenStack cluster.
Normally a system adminstrator would do that part. 

- Installing the Ferry image :ref:`instructions <openstack>`

Once that's done, we can launch our Ferry client. 

Launch Summary
--------------

1. Launch a new Ferry client using the Ferry server image
2. Set OpenStack credentials
3. Create a new Ferry configuration file
4. Start the Ferry server as root via `sudo ferry server`

Launching the Client
--------------------

This documentation assumes that the Ferry client is launched from a VM running in
the OpenStack cluster. This isn't strictly necessary however. If you already have Ferry
installed on your local machine, you can skip this step and begin setting up
your OpenStack credentials. 

1. Start by launching a new instance using the Ferry server image. If you don't know the
name of the image, ask your system adminstrator (it's probably named something like "Ferry Server")
2. Use an instance type with more than 10GB of root storage. 
3. Associate a floating IP with the instance so that can ssh into it later. 

The Ferry image is based on an Ubuntu 14.04 image, so after the instance is fully launched, log in
using the `ubuntu` account.

.. code-block:: bash

    $ ssh -i myprivatekey.pem ubuntu@172.x.x.y 

The next step is to configure your OpenStack credentials. 

Setting OpenStack credentials
-----------------------------

In order to use the OpenStack backend, you'll need to set your OpenStack credentials. Right now
Ferry requires that you run everything as *root*. So switch to the root user (or equivalently use `sudo`). 
Afterwards, set the following environment variables:

- OS_USERNAME
- OS_PASSWORD
- OS_TENANT_ID
- OS_TENANT_NAME
- OS_REGION_NAME
- OS_AUTH_URL

These values can be readily found using the OpenStack Horizon web interface.

Configuring the Client
----------------------

After setting your OpenStack environment variables, you need to create a new Ferry configuration file. 
Create a new file called  `/root/.ferry-config.yaml` and use the following example to populate it. 

.. code-block:: yaml

    system:
      provider: openstack
      network: eth0
      backend: ferry.fabric.cloud/CloudFabric
      mode: ferry.fabric.openstack.singlelauncher/SingleLauncher
      proxy: false
    openstack:
      params:
        dc: homedc
        zone: ZONE
      deploy:
         image: Ferry Server
         personality: standard.small
         default-user: ubuntu
         ssh: ferry-keys
         ssh-user: ferry
      homedc:
         region: REGION
         keystone: https://<IDENTITYSERVICE>.com
         neutron: https://<NETWORKSERVICE>.com
         nova: https://<COMPUTESERVICE>.com
         swift: https://<STORAGESERVICE>.com
         cinder: https://<DISKSERVICE>.com
         heat: https://<ORCHSERVICE>.com
         extnet: 123-123-123
         network: 123-123-123
         router: 123-123-123


First let's fill in the `openstack.params.zone` and `openstack.homedc.region` values.

- `openstack.params.zone` : the default availability zone
- `openstack.homedc.region` : the default region 

Next we need to supply the OpenStack service endpoints. 

- `openstack.homedc.keystone` : location of the identity service
- `openstack.homedc.neutron` : location of the network service
- `openstack.homedc.nova` : location of the compute service
- `openstack.homedc.swift` : location of the storage service
- `openstack.homedc.cinder` : location of the block storage service
- `openstack.homedc.heat` : location of the orchestration service (optional)

Now, under `openstack` and `homedc`, there are three fields called `extnet`, `network`, and `router`. To fill in these
values, you can use the `ferry-install os-info` command. Just type that in and you should see
something like this:

.. code-block:: bash

    $ ferry-install os-info
    ====US West====
    Networks:
    +--------------------------------------+----------------+--------------------------------------------------+
    | id                                   | name           | subnets                                          |
    +--------------------------------------+----------------+--------------------------------------------------+
    | 122c72de-0924-4b9f-8cf3-b18d5d3d292c | Ext-Net        | c2ca2626-97db-429a-bb20-1ea42e13e033             |
    | 11111111-2222-3333-4444-555555555555 | myuser-network | 1111111111111-2222-3333-444444444444 10.0.0.0/24 |
    +--------------------------------------+----------------+--------------------------------------------------+
    Routers:
    +--------------------------------------+---------------+-----------------------------------------------------------------------------+
    | id                                   | name          | external_gateway_info                                                       |
    +--------------------------------------+---------------+-----------------------------------------------------------------------------+
    | 11111111-2222-3333-4444-555555555555 | myuser-router | {"network_id": "122c72de-0924-4b9f-8cf3-b18d5d3d292c", "enable_snat": true} |
    +--------------------------------------+---------------+-----------------------------------------------------------------------------+

Just copy the the ID of the `Ext-Net`, `myuser-network` and `myuser-router` into the respective `extnet`, `network` and `router` fields.

Next you need to configure your ssh key. 

- `openstack.deploy.ssh` : name of the ssh key you'd like to use for VM creation 

On your client, you'll need to place a  copy of the private key placed in the `/ferry/keys/` directory.

Finally, here are the list of optional values that you can set.

- `system.proxy` : set to `true` if you're running your client in the OpenStack cluster.
- `openstack.deploy.personality` : the default personality to use. Highly recommended to use an image with more than 2 virtual CPUs. 

Running Examples
----------------

After you've created your configuration file, you should start the Ferry server:

.. code-block:: bash

    $ sudo ferry server

It'll take a few seconds, but you'll eventually see output that indicates that you're using the OpenStack
backend. 

.. code-block:: bash

    $ sudo ferry server
    ...
    using heat server http://10.1.0.3:8004/v1/42396664178112
    using backend cloud ver:0.1

Afterwards, you should be able to start a new application stack. 

.. code-block:: bash

    $ sudo ferry start hadoop

Starting the Hadoop stack can take 10 minutes or longer. If you login to your Horizon web interface, 
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
