import os
import os.path
from pyspark.mllib.classification import LogisticRegressionWithSGD
from numpy import array

# Find the test data
spark_home = os.environ['SPARK_HOME']
data_file = os.path.join(spark_home, 'mllib/data/sample_svm_data.txt')

# Load and parse the data
data = sc.textFile(data_file)
parsedData = data.map(lambda line: array([float(x) for x in line.split(' ')]))
model = LogisticRegressionWithSGD.train(parsedData)

# Build the model
labelsAndPreds = parsedData.map(lambda point: (int(point.item(0)),
        model.predict(point.take(range(1, point.size)))))

# Evaluating the model on training data
trainErr = labelsAndPreds.filter(lambda (v, p): v != p).count() / float(parsedData.count())
print("Training Error = " + str(trainErr))
