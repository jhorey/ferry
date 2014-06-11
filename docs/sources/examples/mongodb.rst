:title: MongoDB example
:description: A simple example using MongoDB
:keywords: ferry, example, mongodb

.. _mongodb:

Getting started with MongoDB
============================

MongoDB is a popular document store that makes it super simple store, retrieve, and analyze 
JSON-based datasets. It is often used as a transactional store for web applications. Although
it's not strictly a "big data" tool, it is an important element in many applications. 

To get started, let's define our stack in a file (let's call it ``mongo.yaml``). 
The file should look something like this:

.. code-block:: yaml

   backend:
      - storage:
           personality: "mongodb"
           instances: 1
   connectors:
      - personality: "ferry/mongodb-client"

Although MongoDB does support sharding for scalability, Ferry currently does not support this (as of version 0.2.2). 
Consequently, you probably want just a single instance of MongoDB. 

Running an example
------------------

Once you have the application defined, go ahead and start it. Once it's started login to your client to see what
environment variables have been populated by MongoDB. 

.. code-block:: bash

   $ env | grep BACKEND
   BACKEND_STORAGE_TYPE=mongodb
   BACKEND_STORAGE_MONGO=10.1.0.1
   BACKEND_STORAGE_MONGO_PASS=eec68b55-9819-4461-bb55-f1494cfe364e
   BACKEND_STORAGE_MONGO_USER=9b845bdf-657c-4402-ac45-c08a3c91e3d8

Note that MongoDB by default generates a random username and password for authentication. You'll need to pass those values
into your client before accessing MongoDB. 

More resources
--------------

As mentioned, MongoDB is often used in combination with another data store that's more focused on analytics, such as 
Hadoop or GlusterFS. :ref:`Here's <multiple>` where to learn how to create a multi-storage application. Also, here
are a few links for additional MongoDB documentation.  

- `MongoDB <http://www.mongodb.org/>`_

