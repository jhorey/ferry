#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

if [ $1 == "master" ]; then
    su ferry -c '$SPARK_HOME/sbin/start-master.sh' >> /tmp/spark.log 2>> /tmp/spark.err
    su ferry -c '$SPARK_HOME/sbin/start-slaves.sh' >> /tmp/spark.log 2>> /tmp/spark.err
fi
