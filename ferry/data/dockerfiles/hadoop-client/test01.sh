#!/bin/bash

if [ $1 == "tera" ]; then
	su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar teragen 256 /service/data/teragen-output'
	su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar terasort /service/data/teragen-output /service/data/terasort-output'
elif [ $1 == "text" ]; then
	su drydock -c 'wget http://www.gutenberg.org/cache/epub/20417/pg20417.txt -P /tmp/example-text/'
	su drydock -c 'wget http://www.gutenberg.org/cache/epub/5000/pg5000.txt -P /tmp/example-text/'
	su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf dfs -copyFromLocal /tmp/example-text /service/data/example-text'
	su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar wordcount /service/data/example-text /service/data/wordcount-output'/
	su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar wordmean /service/data/example-text /service/data/wordmean-output'
	su drydock -c '/service/packages/hadoop/bin/hadoop --config /service/conf jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar wordmedian /service/data/example-text /service/data/wordmedian-output'
elif [ $1 == "hive" ]; then
	su drydock -c 'wget http://files.grouplens.org/datasets/movielens/ml-100k/u.data -P /tmp/movielens/'
	su drydock -c '/service/packages/hadoop/bin/hdfs dfs -mkdir -p /service/data/movielens'
	su drydock -c '/service/packages/hadoop/bin/hdfs dfs -copyFromLocal /tmp/movielens/u.data /service/data/movielens'
	su drydock -c '/service/packages/hive/bin/hive -f /service/scripts/createtable.sql'
elif [ $1 == "dfs" ]; then
	su drydock -c '/service/packages/hadoop/bin/hadoop dfsadmin -report'
fi