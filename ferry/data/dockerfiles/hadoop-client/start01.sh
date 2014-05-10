#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

if [ $1 == "hadoop" ]; then
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir /tmp'
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /tmp'
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir -p /service/data/hive'
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /service/data/hive'
elif [ $1 == "gluster" ]; then 
	python /service/scripts/mounthelper.py umount
	python /service/scripts/mounthelper.py mount $2
	chown -R ferry:docker /service/data
fi