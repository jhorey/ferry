import os
import os.path
from pyspark.mllib.clustering import KMeans
from numpy import array
from math import sqrt

# Find the test data
spark_home = os.environ['SPARK_HOME']
data_file = os.path.join(spark_home, 'data/kmeans_data.txt')

# Load and parse the data
data = sc.textFile(data_file)
parsedData = data.map(lambda line: array([float(x) for x in line.split(' ')]))

# Build the model (cluster the data)
clusters = KMeans.train(parsedData, 2, maxIterations=10,
        runs=30, initialization_mode="random")

# Evaluate clustering by computing Within Set Sum of Squared Errors
def error(point):
    center = clusters.centers[clusters.predict(point)]
    return sqrt(sum([x**2 for x in (point - center)]))

WSSSE = parsedData.map(lambda point: error(point)).reduce(lambda x, y: x + y)
print("Within Set Sum of Squared Error = " + str(WSSSE))
