#!/bin/bash

source /etc/profile

# 
# Basic start script for Open MPI clients. 
# This script is executed whenever the container starts.
# 

# First we should unmount previous filesystems. This might happen
# if we started a snapshotted image.
python /service/sbin/mounthelper.py umount

# Mount GlusterFS and set the owner as 'ferry' user. 
python /service/sbin/mounthelper.py mount $1
chown -R ferry:docker /service/data