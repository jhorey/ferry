#!/bin/bash

# Unmount gluster if necessary
if [ $1 == "gluster" ]; then 
	python /service/scripts/mounthelper.py umount
fi

# Now stop the ssh daemon. 
pkill -f sshd