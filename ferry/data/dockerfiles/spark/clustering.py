import os
import os.path
import sys
from pyspark import SparkContext
from pyspark.mllib.clustering import KMeans
from numpy import array
from math import sqrt

# Evaluate clustering by computing Within Set Sum of Squared Errors
def error(point):
    center = clusters.centers[clusters.predict(point)]
    return sqrt(sum([x**2 for x in (point - center)]))

if __name__ == "__main__":
    data_file = '/spark/data/kmeans.txt'

    if len(sys.argv) == 1:
        print >> sys.stderr, "Usage: filtering.py <master>"
        exit(-1)
    else:
        # Load and parse the data
        sc = SparkContext(sys.argv[1], "KMeans Clustering")
        data = sc.textFile(data_file)
        parsedData = data.map(lambda line: array([float(x) for x in line.split(' ')]))

        # Build the model (cluster the data)
        clusters = KMeans.train(parsedData, 2, maxIterations=10,
                                runs=30, initialization_mode="random")


        WSSSE = parsedData.map(lambda point: error(point)).reduce(lambda x, y: x + y)
        print("Within Set Sum of Squared Error = " + str(WSSSE))
