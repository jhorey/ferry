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
	script=$2
	run_as_ferry '$SPARK_HOME/bin/pyspark /service/examples/python/${script} spark://$BACKEND_COMPUTE_MASTER:7077' 'Running ${script}'
    fi
elif [ $1 == "example" ]; then
    run_as_ferry '$SPARK_HOME/bin/run-example org.apache.spark.examples.SparkPi spark://$BACKEND_COMPUTE_MASTER:7077'
fi