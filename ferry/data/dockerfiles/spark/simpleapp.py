import os
import os.path
from pyspark import SparkContext

if 'BACKEND_COMPUTE_MASTER' in os.environ:
    master = os.environ['BACKEND_COMPUTE_MASTER']
else:
    master = 'localhost'

logFile = os.path.join("/tmp/data/README.md")

from pyspark import SparkConf, SparkContext
conf = SparkConf()
conf.setMaster('spark://' + master + ':7077')
conf.setAppName("simpleapp")
sc = SparkContext(conf = conf)
logData = sc.textFile(logFile).cache()

numAs = logData.filter(lambda s: 'a' in s).count()
numBs = logData.filter(lambda s: 'b' in s).count()

print "Lines with a: %i, lines with b: %i" % (numAs, numBs)
