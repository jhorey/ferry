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

if [ $1 == "tera" ]; then
    TERAGEN='hadoop jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar teragen 256 /service/data/teragen-output'
    TERASORT='hadoop jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar terasort /service/data/teragen-output /service/data/terasort-output'
    run_as_ferry "$TERAGEN" "Running Teragen"
    run_as_ferry "$TERASORT" "Running Terasort"
elif [ $1 == "text" ]; then
    WGET1='wget http://www.gutenberg.org/cache/epub/20417/pg20417.txt -P /tmp/example-text/'
    WGET2='wget http://www.gutenberg.org/cache/epub/5000/pg5000.txt -P /tmp/example-text/'
    COPY='hadoop dfs -copyFromLocal /tmp/example-text /service/data/example-text'
    WORDCOUNT='hadoop jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar wordcount /service/data/example-text /service/data/wordcount-output'
    WORDMEAN='hadoop jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar wordmean /service/data/example-text /service/data/wordmean-output'
    WORDMEDIAN='hadoop jar /service/packages/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-2.3.0.jar wordmedian /service/data/example-text /service/data/wordmedian-output'

    run_as_ferry "$WGET1" "Downloading first text"
    run_as_ferry "$WGET2" "Downloading second text"
    run_as_ferry "$COPY" "Copy text to HDFS"
    run_as_ferry "$WORDCOUNT" "Running word count"
    run_as_ferry "$WORDMEAN" "Running word mean"
    run_as_ferry "$WORDMEDIAN" "Running word median"
elif [ $1 == "hive" ]; then
    WGET='wget http://files.grouplens.org/datasets/movielens/ml-100k/u.data -P /tmp/movielens/'
    MKDIR='hdfs dfs -mkdir -p /service/data/movielens'
    COPY='hdfs dfs -copyFromLocal /tmp/movielens/u.data /service/data/movielens'
    HIVE='hive -f /service/scripts/createtable.sql'

    run_as_ferry "$WGET" "Downloading movielens dataset"
    run_as_ferry "$MKDIR" "Making movielens directory"
    run_as_ferry "$COPY" "Copy data to HDFS"
    run_as_ferry "$HIVE" "Running Hive"
elif [ $1 == "pig" ]; then
    WGET='wget http://files.grouplens.org/datasets/movielens/ml-100k/u.data -P /tmp/movielens/'
    MKDIR='hdfs dfs -mkdir -p /service/data/movielens'
    COPY='hdfs dfs -copyFromLocal /tmp/movielens/u.data /service/data/movielens'
    PIG='pig -f /service/scripts/count.pig'

    run_as_ferry "$WGET" "Downloading movielens dataset"
    run_as_ferry "$MKDIR" "Making movielens directory"
    run_as_ferry "$COPY" "Copy data to HDFS"
    run_as_ferry "$PIG" "Running Pig command"
elif [ $1 == "gluster" ]; then
    WGET='wget http://files.grouplens.org/datasets/movielens/ml-100k/u.data -P /service/data/movielens/'
    HIVE='hive -f /service/scripts/createtable.sql'

    run_as_ferry "$WGET" "Downloading movielens dataset"
    run_as_ferry "$HIVE" "Running Hive"
elif [ $1 == "dfs" ]; then
    DFS='hadoop dfsadmin -report'
    run_as_ferry "$DFS" "Running HDFS report"
fi