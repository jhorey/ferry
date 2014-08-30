:title: Ferry OpenStack Installation
:description: Installing Ferry on your OpenStack cluster
:keywords: ferry, installation, openstack

.. _openstack:

OpenStack Server Installation
=============================

This documentation is meant for system adminstrators and data engineers that are interested 
in installing Ferry in their own OpenStack private cloud. If you're an end-user, you probably
want to read :ref:`this <hpcloud>`. 

Installing Ferry on your OpenStack cluster is relatively straightfoward, and simply requires
creating a "Ferry Server" image. 

Quick Installation 
-------------------

1. Instantiate an Ubuntu 14.04 image 
2. Create a `/ferry/master` directory and export "FERRY_DIR=/ferry/master"
3. Install Ferry and all Ferry images
4. Save the image as "Ferry Server (small)"

Ubuntu 14.04
------------

The Ferry server must be based on Ubuntu 14.04. If your OpenStack cluster 
does not have an Ubuntu 14.04 image already, you can download an image from
the Ubuntu website:

- `Ubuntu 14.04 Cloud Image <https://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img/>`_ 

Afterwards you can import the image into Glance by typing: 
Once you have an Ubuntu 14.04 instance running, 

.. code-block:: bash

    $ glance image-create --name "Ubuntu 14.04 (amd64)" --disk-format=raw --container-format=bare --file=./trusty-server-cloudimg-amd64-disk1.img

After importing the image, boot up a new Ubuntu instance. You'll want to use an instance type with at least a 10GB root directory, since
we'll be installing all the Ferry images. 

Installing Ferry
----------------

After instantiating the Ubuntu instance, you'll need to install Ferry. The easiest way is to use our automated installation script:

.. code-block:: bash

    $ git clone https://github.com/opencore/ferry.git
    $ sudo ferry/install/ferry-install

However you can also install Ferry manually.

- Detailed Ferry :ref:`instructions <client>`

One point of note: you'll need to first create and set an alternative Ferry data directory. 

.. code-block:: bash

    $ mkdir -p /ferry/master && export FERRY_DIR=/ferry/master

The installation process can take quite a while (it will download approximately
5GB of Docker images). 

To verify if Ferry has been installed, you can just type:

.. code-block:: bash

    $ sudo ferry server
    ...
    using backend local
    $ sudo ferry ps
    UUID        Storage     Compute     Connectors      Status         Base       Time
    ----        -------     -------     ----------      ------         ----       ----

OpenStack Heat
--------------

Ferry uses the Heat orchestration engine to launch clusters on OpenStack. If your
OpenStack cluster already has Heat installed, then you can skip this step. Otherwise, Ferry
will use its own "stand-alone" Heat server. To use the stand-alone Heat server, you'll need 
to download the Ferry Heat image. 

.. code-block:: bash

    $ sudo ferry server
    $ sudo ferry pull image://ferry/heatserver

Save Image
----------

Now that you have Ferry installed, go ahead and stop Ferry.  

.. code-block:: bash

    $ sudo ferry quit

Afterwards, create a *snapshot* of the instance. You can name the
snapshot whatever you want, but users will need this name later when configuring the client. 
Something like "Ferry Server" should do. 

Next Steps
----------

Once the Ferry image is created, users should be able to start using Ferry to create 
big data clusters. The "Ferry Server" image can be used either as a client or server. 

- Configuring the client :ref:`instructions <osclient>`
- HP Cloud client :ref:`instructions <hpcloud>`

