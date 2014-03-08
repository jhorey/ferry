#!/bin/bash

# Prerequisites
apt-get --yes install unzip
su drydock -c 'mkdir /tmp/build'
su drydock -c 'mkdir /tmp/src'
su drydock -c 'mkdir /tmp/text'
su drydock -c 'export PATH=$PATH:$HADOOP_HOME/bin'

# Compile the example Wordcount application
su drydock -c 'cp /service/packages/hadoop/share/hadoop/mapreduce/sources/hadoop-mapreduce-examples-2.3.0-sources.jar /tmp/src'
su drydock -c 'cd /tmp/src; unzip hadoop-mapreduce-examples-2.3.0-sources.jar'
su drydock -c 'javac -cp `hadoop classpath`:. -d /tmp/build org/apache/hadoop/examples/WordCount.java'
su drydock -c 'cd /tmp/build; jar cf WordCount.jar org/apache/hadoop/examples/WordCount.class'

# Execute the example Wordcount application
su drydock -c 'wget http://www.gutenberg.org/cache/epub/20417/pg20417.txt -P /tmp/text/'
su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf dfs -copyFromLocal /tmp/text /service/data/example-text'
su drydock -c 'hadoop jar WordCount.jar org.apache.hadoop.examples.WordCount /service/data/example-text /service/data/wordcount-output'