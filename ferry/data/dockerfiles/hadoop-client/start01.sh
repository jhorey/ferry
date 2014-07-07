#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

if [ $1 == "hadoop" ]; then
    #
    # This Hadoop cluster is using the HDFS backend. That means
    # we need to create various directories in HDFS for Hive, and
    # forward all web interfaces. 
    #
    su ferry -c "nohup python /service/scripts/proxy.py $BACKEND_STORAGE_YARN 8088 &" >> /tmp/hadoop.log 2>> /tmp/hadoop.err
    su ferry -c "nohup python /service/scripts/proxy.py $BACKEND_STORAGE_YARN 19888 &" >> /tmp/hadoop.log 2>> /tmp/hadoop.err
    su ferry -c "nohup python /service/scripts/proxy.py $BACKEND_STORAGE_HDFS 50070 &" >> /tmp/hadoop.log 2>> /tmp/hadoop.err

    su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir /tmp' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
    su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /tmp' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
    su ferry -c '/service/packages/hadoop/bin/hdfs dfs -mkdir -p /service/data/hive' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
    su ferry -c '/service/packages/hadoop/bin/hdfs dfs -chmod g+w /service/data/hive' >> /tmp/hadoop.log 2>> /tmp/hadoop.err
elif [ $1 == "gluster" ]; then 
    #
    # This Hadoop cluster is using the GlusterFS backend. That means
    # we need to mount the volume and forward the YARN web intefaces. 
    #
    su ferry -c "nohup python /service/scripts/proxy.py $BACKEND_STORAGE_YARN 8088 &" >> /tmp/hadoop.log 2>> /tmp/hadoop.err
    su ferry -c "nohup python /service/scripts/proxy.py $BACKEND_STORAGE_YARN 19888 &" >> /tmp/hadoop.log 2>> /tmp/hadoop.err

    python /service/scripts/mounthelper.py umount
    python /service/scripts/mounthelper.py mount $2
    chown -R ferry:docker /service/data
fi
