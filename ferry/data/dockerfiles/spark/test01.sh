#!/bin/bash

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
	shift # Get rid of the first arg. 
	shift # Get rid of the second arg.
	run_as_ferry '$SPARK_HOME/bin/pyspark $SPARK_HOME/python/examples/${script} spark://$BACKEND_COMPUTE_MASTER:7077 $@' 'Running ${script}'
    fi
elif [ $1 == "example" ]; then
    run_as_ferry '$SPARK_HOME/bin/run-example org.apache.spark.examples.SparkPi spark://$BACKEND_COMPUTE_MASTER:7077'
fi