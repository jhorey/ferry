#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

if [ $1 == "master" ]; then
    su ferry -c '$SPARK_HOME/sbin/start-master.sh'
    su ferry -c '$SPARK_HOME/sbin/start-slaves.sh'
fi