import os
import os.path
import sys
from pyspark import SparkContext
from pyspark.mllib.classification import LogisticRegressionWithSGD
from numpy import array

if __name__ == "__main__":
    data_file = '/spark/data/svm.txt'

    if len(sys.argv) == 1:
        print >> sys.stderr, "Usage: classification.py <master>"
        exit(-1)
    else:
        # Load and parse the data
        sc = SparkContext(sys.argv[1], "Binary Classification")
        data = sc.textFile(data_file)
        parsedData = data.map(lambda line: array([float(x) for x in line.split(' ')]))
        model = LogisticRegressionWithSGD.train(parsedData)

        # Build the model
        labelsAndPreds = parsedData.map(lambda point: (int(point.item(0)),
                                                       model.predict(point.take(range(1, point.size)))))

        # Evaluating the model on training data
        trainErr = labelsAndPreds.filter(lambda (v, p): v != p).count() / float(parsedData.count())
        print("Training Error = " + str(trainErr))
