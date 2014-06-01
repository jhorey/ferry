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

# Make a copy of the communication keys to a
# shared directory.
if [[ $2 == "master" ]]; then
    if [[ ! -e /service/data/.comkeys ]]; then
	mkdir /service/data/.comkeys
    fi
    cp /home/ferry/.ssh/id_rsa* /service/data/.comkeys/
fi    