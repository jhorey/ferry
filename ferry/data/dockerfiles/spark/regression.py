import os
import os.path
import sys
from pyspark import SparkContext
from pyspark.mllib.regression import LabeledPoint, LinearRegressionWithSGD
from numpy import array

# Load and parse the data
def parsePoint(line):
    values = [float(x) for x in line.replace(',', ' ').split(' ')]
    return LabeledPoint(values[0], values[1:])

if __name__ == "__main__":
    data_file = '/spark/data/lpsa.data'

    if len(sys.argv) == 1:
        print >> sys.stderr, "Usage: regression.py <master>"
        exit(-1)
    else:
        # Load and parse the data
        sc = SparkContext(sys.argv[1], "Logistic Regression")
        data = sc.textFile(data_file)
        parsedData = data.map(parsePoint)

        # Build the model
        model = LinearRegressionWithSGD.train(parsedData)

        # Evaluate the model on training data
        valuesAndPreds = parsedData.map(lambda p: (p.label, 
                                                   model.predict(p.features)))
        MSE = valuesAndPreds.map(lambda (v, p): (v - p)**2).reduce(lambda x, y: x + y) / valuesAndPreds.count()
        print("Mean Squared Error = " + str(MSE))
