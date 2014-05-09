import os
import os.path
import sys
from pyspark import SparkContext
from pyspark.mllib.regression import LinearRegressionWithSGD
from numpy import array

if __name__ == "__main__":
    data_file = '/spark/data/lpsa.data'

    if len(sys.argv) == 1:
        print >> sys.stderr, "Usage: regression.py <master>"
        exit(-1)
    else:
        # Load and parse the data
        sc = SparkContext(sys.argv[1], "Logistic Regression")
        data = sc.textFile(data_file)
        parsedData = data.map(lambda line: array([float(x) for x in line.replace(',', ' ').split(' ')]))

        # Build the model
        model = LinearRegressionWithSGD.train(parsedData)

        # Evaluate the model on training data
        valuesAndPreds = parsedData.map(lambda point: (point.item(0),
                                                       model.predict(point.take(range(1, point.size)))))
        MSE = valuesAndPreds.map(lambda (v, p): (v - p)**2).reduce(lambda x, y: x + y)/valuesAndPreds.count()
        print("Mean Squared Error = " + str(MSE))
