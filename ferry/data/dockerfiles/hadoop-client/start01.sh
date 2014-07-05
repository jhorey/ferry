#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

if [ $1 == "hadoop" ]; then
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir /tmp' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /tmp' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir -p /service/data/hive' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /service/data/hive' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
elif [ $1 == "gluster" ]; then 
	python /service/scripts/mounthelper.py umount
	python /service/scripts/mounthelper.py mount $2
	chown -R ferry:docker /service/data
fi
