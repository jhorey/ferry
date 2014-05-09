import os
import os.path
from pyspark.mllib.regression import LinearRegressionWithSGD
from numpy import array

# Find the test data
spark_home = os.environ['SPARK_HOME']
data_file = os.path.join(spark_home, 'mllib/data/ridge-data/lpsa.data')

# Load and parse the data
data = sc.textFile(data_file)
parsedData = data.map(lambda line: array([float(x) for x in line.replace(',', ' ').split(' ')]))

# Build the model
model = LinearRegressionWithSGD.train(parsedData)

# Evaluate the model on training data
valuesAndPreds = parsedData.map(lambda point: (point.item(0),
        model.predict(point.take(range(1, point.size)))))
MSE = valuesAndPreds.map(lambda (v, p): (v - p)**2).reduce(lambda x, y: x + y)/valuesAndPreds.count()
print("Mean Squared Error = " + str(MSE))
