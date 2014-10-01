#!/bin/bash

#
# Run some simple Spark examples.
# Examples can be found in the following directories:
# - /service/examples/python
# - $SPARK_HOME/examples
# 

# Bash colors
GREEN='\e[0;32m'
NC='\e[0m'

function run_as_ferry {
    echo -e "${GREEN} ${2} ${NC}"
    if [ $USER == "root" ]; then
	su ferry -c "$1"
    else
	$1
    fi
}

source /etc/profile
if [ $1 == "python" ]; then
    if [ $# == 2 ]; then
	run_as_ferry "$SPARK_HOME/bin/pyspark /service/examples/python/$2 spark://$BACKEND_COMPUTE_MASTER:7077" "Running $2"
    fi
elif [ $1 == "load" ]; then
    MKDIR='hdfs dfs -mkdir -p /spark/data'
    COPY1='hdfs dfs -copyFromLocal /service/examples/data/als/test.data /spark/data/als.data'
    COPY2='hdfs dfs -copyFromLocal /service/examples/data/sample_svm_data.txt /spark/data/svm.txt'
    COPY3='hdfs dfs -copyFromLocal /service/examples/data/ridge-data/lpsa.data /spark/data/lpsa.data'
    COPY4='hdfs dfs -copyFromLocal /service/examples/data/kmeans_data.txt /spark/data/kmeans.txt'

    run_as_ferry "$MKDIR" "Making Spark data directories"
    run_as_ferry "$COPY1" "Upload dataset 1"
    run_as_ferry "$COPY2" "Upload dataset 2"
    run_as_ferry "$COPY3" "Upload dataset 3"
    run_as_ferry "$COPY4" "Upload dataset 4"
elif [ $1 == "example" ]; then
    run_as_ferry '$SPARK_HOME/bin/spark-submit --class org.apache.spark.examples.SparkPi --master spark://$BACKEND_COMPUTE_MASTER:7077 $SPARK_HOME/lib/spark-examples-1.1.0-hadoop2.4.0.jar'
fi
