#!/bin/bash

source /service/sbin/setup

# Unmount gluster if necessary
if [ $1 == "gluster" ]; then 
	python /service/scripts/mounthelper.py umount
fi
