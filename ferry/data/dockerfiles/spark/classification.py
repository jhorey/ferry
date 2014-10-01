import os
import os.path
import sys
from pyspark import SparkContext
from pyspark.mllib.classification import LogisticRegressionWithSGD
from pyspark.mllib.regression import LabeledPoint
from numpy import array

if __name__ == "__main__":
    data_file = '/spark/data/svm.data'

    if len(sys.argv) == 1:
        print >> sys.stderr, "Usage: classification.py <master>"
        exit(-1)
    else:
        # Load and parse the data
        sc = SparkContext(sys.argv[1], "Binary Classification")
        data = sc.textFile(data_file)
        parsedData = data.map(lambda line: array([float(x) for x in line.split(' ')]))
        model = LogisticRegressionWithSGD.train(parsedData)

        # Build the model and evaluate on training data. 
        labelsAndPreds = parsedData.map(lambda p: (p.label, model.predict(p.features)))
        trainErr = labelsAndPreds.filter(lambda (v, p): v != p).count() / float(parsedData.count())
        print("Training Error = " + str(trainErr))
