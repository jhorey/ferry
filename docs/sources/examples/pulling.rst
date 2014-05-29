:title: Pulling new applications
:description: How to push and pull new applications
:keywords: ferry, example 

.. _pulling:

Ferry lets you easily share your application with others. 


Pushing Applications
====================

Once you're done developing your app, you can upload your application to the Ferry servers to share it with others. 
For now, you'll need an account on Docker.io to upload your images and another on Ferry to store your application stack. Once
you have these accounts, you'll need to create an *authorization* file. 

.. code-block:: bash

    $ cat ~/.ferry.docker
    docker:
         user: <DOCKER LOGIN>
         password: <DOCKER PASSWORD>
         email: <DOCKER EMAIL>
         server: https://index.docker.io/v1/
    ferry:
         user: <FERRY LOGIN>
         key: <FERRY KEY>
         server: http://apps.opencore.io
         registry: docker

Note that currently all Ferry applications are *public*. It doesn't necessarily mean that all your customizations are publicly accessible, 
just that anybody can download your application. Private applications are something that we plan on supporting in the near future. 

To upload the application, just perform a *push* command and point it to your application stack. 

.. code-block:: bash

    $ ferry push app:///home/ferry/mortar.yml
    opencore/mortar

The final name of the application is your Ferry user name appended with the name of the application file. 

Pulling Applications
====================

To download an application, you'll want to perform a *pull* command. Ferry lets you download Docker images manually or an entire Ferry application. Here
we're going to pull the *Mortar Recommendation System* application. 

.. code-block:: bash

    $ sudo ferry pull app://opencore/mortar
    $ ferry inspect opencore/mortar
    backend:
       - storage:
            personality: "hadoop"
            instances: ">=1"
            layers:
               - "hive"
    connectors:
       - personality: "ferry/mortar-recsys"

This will pull all the Docker images the application needs and will register the
application on your local machine. If you just want to download an *image*, just type:

.. code-block:: bash

    $ sudo ferry pull image://opencore/mortar-recsys

Once you downloaded the application, you can start it like
any other application:

.. code-block:: bash

    $ ferry start opencore/mortar
