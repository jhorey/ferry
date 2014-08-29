:title: Ferry on HP Cloud
:description: Running Ferry on HP OpenStack Cloud
:keywords: ferry, installation, openstack, hpcloud

.. _hpcloud:

HP Cloud
========

HP Cloud is based on OpenStack and is fully supported by Ferry. In fact, all the
Ferry images are pre-installed making it relatively straightforward to get started. 

Launch Summary
--------------

- Launch a new Ferry client using the "Ferry Server (small)" image
- Set OpenStack credentials
- Create a new Ferry configuration file
- Start the Ferry server as root via `sudo ferry server`
- Create new Hadoop cluster via `sudo ferry start hadoop`

Launching the Client
--------------------

This documentation assumes that the Ferry client is launched from a VM running in
the HP Cloud. This isn't strictly necessary however. If you already have Ferry
installed on your local machine, you can skip this step and begin setting up
your OpenStack credentials. 

If you're launching a new Ferry client, OpenCore provides pre-built images for HP Cloud. 

- Start by launching a new instance using the "Ferry Server (small)" image.
- Use at least the "standard.small" instance size
- Associate a floating IP with the instance so that can ssh into it later. 

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

These values can be readily found using the HP Cloud web interface . OS_TENANT_ID and OS_TENANT_NAME can be found under "Identity, Projects". 
OS_REGION_NAME should be set to either `region-a.geo-1` (for US West) or `region-b.geo-1` for (US East). Finally, you can find the
OS_AUTH_URL under "Project, Access & Security, API Access". Specifically, you'll want the URL for the "Identity" service. 

Configuring the Client
----------------------

After setting your OpenStack environment variables, you need to create a new Ferry configuration file. If you're running your
client using the HP Cloud image, just open the file `/root/.ferry-config.yaml`. Otherwise, go ahead and create the file now. 

You want your configuration to look like this: 

.. code-block:: yaml

    system:
      provider: hp
      network: eth0
      backend: ferry.fabric.cloud/CloudFabric
      mode: ferry.fabric.openstack.singlelauncher/SingleLauncher
      proxy: false
    hp:
      params:
        dc: uswest
        zone: az2
      deploy:
         image: Ferry Server (small)
         personality: standard.small
         default-user: ubuntu
         ssh: ferry-keys
         ssh-user: ferry
      uswest:
         region: region-a.geo-1
         keystone: https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
         neutron: https://region-a.geo-1.network.hpcloudsvc.com
         nova: https://region-a.geo-1.compute.hpcloudsvc.com/v2/10089763026941
         swift: https://region-a.geo-1.images.hpcloudsvc.com:443/v1.0
         cinder: https://region-a.geo-1.block.hpcloudsvc.com/v1/10089763026941
         extnet: 122c72de-0924-4b9f-8cf3-b18d5d3d292c
         network: 123-123-123
         router: 123-123-123

Let's skip over most of the configuration for now, and focus on the parts that we need
to configure. 

Under `hp` and `uswest`, there are two fields called `network` and `router`. To fill in these
values, you can use the `ferry-install os-info` command. Just type that in and you should see
something like this:

.. code-block:: bash

    $ ssh -i myprivatekey.pem ubuntu@172.x.x.y 
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

Just copy the the ID of the `myuser-network` and `myuser-router` into the `network` and `router` fields.

Next, you need to configure your HP Cloud key. Notice that under `hp` and `deploy`, there's a field
called `ssh`. Replace `ferry-keys` with the name of your HP Cloud key. You'll also need a copy
of the private key placed in the `/ferry/keys/` directory. This key is used by Ferry to connect to
the VMs and to start the various Ferry processes. 

Finally, here are the list of optional values that you can set.

- `system.proxy` : set to `true` if you're running your client in the OpenStack cluster.
- `hp.params.zone` : availability zone (set to `az1`, `az2`, or `az3`)
- `hp.deploy.personality` : the default personality to use. Highly recommended to use `standard.small` or larger

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

Starting the Hadoop stack can take 10 minutes or longer. If you login to your HP Cloud web interface, 
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
