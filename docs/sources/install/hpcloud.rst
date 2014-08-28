:title: Ferry on HP Cloud
:description: Running Ferry on HP Cloud
:keywords: ferry, installation, hpcloud

HP Cloud
========

HP Cloud is based on OpenStack and is fully supported by Ferry. In fact, all the
Ferry images are pre-installed making it relatively straightforward to get started. 

Launch Summary
--------------

- Launch a new Ferry client using the "Ferry Server (xsmall)" image
- Set OpenStack credentials
- Copy and modify the `ferry-hp-example.yaml` configuration
- Start the Ferry server as root via `sudo ferry server`
- Create new Hadoop cluster via `sudo ferry start hadoop`

Launching the Client
--------------------

This documentation assumes that the Ferry client is launched from a VM running in
the HP Cloud. This isn't strictly necessary however. If you already have Ferry
installed on your local machine, you can skip this step and begin setting up
your OpenStack credentials. 

If you're launching a new Ferry client, OpenCore provides pre-built images for HP Cloud. 
Start by launching a new instance using the "Ferry Server (xsmall)" image. You'll also want
to associate a floating IP with the instance so that can ssh into it later. 

The Ferry image is based on an Ubuntu 14.04 image, so after the instance is launched, log in
using the `ubuntu` account.

.. code-block:: bash

    $ ssh -i myprivatekey.pem ubuntu@172.x.x.y 

The next step is to configure your OpenStack credentials. 

Setting OpenStack credentials
-----------------------------

In order to use the OpenStack backend, you'll need to set your OpenStack credentials. Specifically,
you should set the following:

- OS_USERNAME
- OS_PASSWORD
- OS_TENANT_ID
- OS_TENANT_NAME
- OS_REGION_NAME
- OS_AUTH_URL

OS_USERNAME and OS_PASSWORD should be set to your login and password. OS_TENANT_ID and OS_TENANT_NAME can be found under "Identity, Projects". 

OS_REGION_NAME

Configuring the Client
----------------------

The first step is to configure your Ferry client to use the OpenStack backend, and
then to configure your HP Cloud credentials. The easiest way to do this is to copy
the `ferry-hp-example.yaml` file (located under `FERRY_HOME/data/conf`). It should
look like this:

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
         image: Ferry Server (xsmall)
         personality: standard.xsmall
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

Let's take a look at the `system` configuration. As you can see, the `provider` field
should match the name of another first-level configuration key (in our case `hp`). 
With the exception of `proxy`, you probably don't want to modify the other fields.

The `proxy` field is used to tell Ferry whether the client is being run within the
OpenStack cluster (in which case the value should be set to `true`), or whether the
client is external to the cluster (the default). When the client is run within the
OpenStack cluster, floating IPs will only be assigned to the connectors. 

Most of the actual `hp` configuration should remain unchanged. However, you will need
to supply valid values for both the `network` field and `router` field. These values are
used to help launch the VM instances into the appropriate network. To find these values,
just type `ferry-install os-info`. 

Running Examples
----------------
