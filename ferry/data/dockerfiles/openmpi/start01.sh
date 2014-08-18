#!/bin/bash

# 
# Basic start script for Open MPI clients. 
# This script is executed whenever the container starts.
# 

source /etc/profile
source /service/sbin/utils

#
# Remount the data directory. 
#
remount $1 $2
