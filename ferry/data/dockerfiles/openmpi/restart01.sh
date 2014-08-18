#!/bin/bash

# 
# Basic restart script for Open MPI clients. 
# This script is executed whenever the container restarts.
# 

source /etc/profile
source /service/sbin/utils

#
# Remount the data directory. 
#
remount $1 $2
