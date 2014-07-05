#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile

if [ $1 == "gluster" ]; then 
    sleep 3
    python /service/scripts/mounthelper.py umount
    python /service/scripts/mounthelper.py mount $2
    chown -R ferry:docker /service/data
fi
