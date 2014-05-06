#!/bin/bash

source /etc/profile

# Prerequisites
apt-get --yes install unzip
su ferry -c 'mkdir /tmp/build'
su ferry -c 'mkdir /tmp/src'
su ferry -c 'mkdir /tmp/text'
su ferry -c 'export PATH=$PATH:$HADOOP_HOME/bin'

# Compile the example Wordcount application
su ferry -c 'cp /service/packages/hadoop/share/hadoop/mapreduce/sources/hadoop-mapreduce-examples-2.3.0-sources.jar /tmp/src'
su ferry -c 'cd /tmp/src; unzip hadoop-mapreduce-examples-2.3.0-sources.jar'
su ferry -c 'javac -cp `hadoop classpath`:. -d /tmp/build org/apache/hadoop/examples/WordCount.java'
su ferry -c 'cd /tmp/build; jar cf WordCount.jar org/apache/hadoop/examples/WordCount.class'

# Execute the example Wordcount application
su ferry -c 'wget http://www.gutenberg.org/cache/epub/20417/pg20417.txt -P /tmp/text/'
su ferry -c '/service/packages/hadoop/bin/hadoop --config /service/conf dfs -copyFromLocal /tmp/text /service/data/example-text'
su ferry -c 'hadoop jar WordCount.jar org.apache.hadoop.examples.WordCount /service/data/example-text /service/data/wordcount-output'