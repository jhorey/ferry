#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

# Copy all the instance addresses and empty the file
# afterwards so we only copy it over once. 
input=/service/conf/instances
host=$(hostname)
while read line
do
	split=( $line )
	name=${split[1]}
	if [ "$host" != "$name" ]; then
	    echo $line >> /etc/hosts
	fi
done < "$input"
echo '' > /service/conf/instances

# Create necessary HDFS directories
if [ $1 == "hadoop" ]; then
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir /tmp'
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /tmp'
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir -p /service/data/hive'
	su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /service/data/hive'
elif [ $1 == "gluster" ]; then 
	python /service/scripts/mounthelper.py mount $2
	chown -R ferry:docker /service/data
fi