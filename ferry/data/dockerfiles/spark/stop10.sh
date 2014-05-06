#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

# Stop the Spark daemons
su ferry -c '$SPARK_HOME/sbin/stop-all.sh'
