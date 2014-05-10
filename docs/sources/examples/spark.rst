:title: Spark example
:description: A simple example using Spark
:keywords: ferry, example, spark

.. _spark:

Getting started with Spark
==========================

Apache Spark is a new parallel, in-memory processing framework from U.C. Berkeley's AMPLab. Spark has two main advantages relative to other similar frameworks. First, because of its in-memory design, Spark is able to run certain computations much faster, for example machine learning algorithms. Second, Spark has a very clean API. Spark is written in Scala, a functional language for the JVM but also has strong support for Python. Having said this, Spark is still compatible with Hadoop and can easily read/write data from HDFS. 
		
The first thing to do is to define our application stack. Let's call our new application stack ``spark.yaml``. 
The file should look something like this:

.. code-block:: yaml

   backend:
      - storage:
           personality: "hadoop"
           instances: 2
        compute:
           - personality: "spark"
             instances: 2
   connectors:
      - personality: "ferry/spark-client"

Note that Spark relies on Hadoop for the actual data storage. Ferry runs Spark in "stand-alone" mode (deeper YARN integration will come in the future). So to create the actual Spark cluster, we'll need to specify the ``compute`` section. Finally, we'll need at least one ``spark-client`` so that we can launch jobs and interact with the rest of the cluster. 

Running an example
------------------

Now that we've defined our stack, let's start it up. Don't forget that you need the Ferry server to be up and running (via ``sudo ferry server``). Afterwards type ``ferry start spark`` into your terminal. ``spark`` should be replaced with the path to your specific file. Otherwise it will use a default Spark
stack. The entire process should take less than a minute. 

Before we continue, let's take a step back to examine what just happened. After typing ``start``, ``ferry`` created the following Docker
containers:

- Two Hadoop data nodes
- Hadoop namenode
- Hadoop YARN resource manager
- Two Spark compute nodes
- A Linux client

Now that the environment is created, let's interact with it by connecting to the Linux client. 
Just type ``ferry ssh sa-0`` (where ``sa-0`` is replaced with your application ID). Once you're logged in, you should be able to run all the examples. Remember, the connector is just a Docker container. That means you can completely customize the environment including installing packages and even modify configuration files. 

Python Examples
---------------

Now we should be able to run Spark jobs. If you're really impatient, you can run some Python examples by typing:

.. code-block:: bash

   $ /service/runscripts/test/test01.sh load
   $ /service/runscripts/test/test01.sh python regression.py

This downloads some data and runs a *linear regression* example over that data. You can check out more examples in the directory */service/examples/python*. Here's a Python example showing how to perform *collaborative filtering* (a popular method for recommendations). 

.. code-block:: python

   import sys
   from pyspark import SparkContext
   from pyspark.mllib.recommendation import ALS
   from numpy import array
   
   if __name__ == "__main__":
       data_file = '/spark/data/als.data'
   
       sc = SparkContext(sys.argv[1], "Collaborative Filtering")
       data = sc.textFile(data_file)
       ratings = data.map(lambda line: array([float(x) for x in line.split(',')]))
   
       # Build the recommendation model using Alternating Least Squares
       model = ALS.train(ratings, 1, 20)
   
       # Evaluate the model on training data
       testdata = ratings.map(lambda p: (int(p[0]), int(p[1])))
       predictions = model.predictAll(testdata).map(lambda r: ((r[0], r[1]), r[2]))
       ratesAndPreds = ratings.map(lambda r: ((r[0], r[1]), r[2])).join(predictions)
       MSE = ratesAndPreds.map(lambda r: (r[1][0] - r[1][1])**2).reduce(lambda x, y: x + y)/ratesAndPreds.count()
       print("Mean Squared Error = " + str(MSE))

As you can see the source is fairly short for what it does. Spark includes the *MLLib* machine-learning library which simplifies creating advanced data mining algorithms. If you specified more than a single node for your Spark cluster, this example will run (virtually) in parallel. 

If you want to run your own Python application, just type the following (as the ``ferry`` user):

.. code-block:: bash

   $ $SPARK_HOME/bin/pyspark my_spark_app.py spark://$BACKEND_COMPUTE_MASTER:7077


More resources
--------------

Once you're done running the built-in examples, check out these additional resources to learn more. 

- `Apache Spark <http://spark.apache.org/>`_
- `U.C. Berkeley Amp Lab <https://amplab.cs.berkeley.edu/>`_

