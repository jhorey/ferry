#!/bin/bash

# Make sure we get the env variables in place. 
source /etc/profile
source /service/sbin/pophosts

pophosts
if [ $1 == "gluster" ]; then 
	python /service/scripts/mounthelper.py mount $2
	chown -R ferry:docker /service/data
fi