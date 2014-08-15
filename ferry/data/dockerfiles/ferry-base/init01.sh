#! /bin/bash

# 
# This the initialization script used by all the Ferry images. The init script is the
# first script run after the container is started. This script should not be modified 
# by the container. 
# 
#

#
# Contains basic functions. 
# 
source /service/sbin/setup

#
# Create the FUSE device. This won't be necessary
# once we upgrade Docker, but keep it as a fail-safe
# 
create_fuse_dev    

#
# Authorize the ssh key so that we can do password-less entry. 
#
cat /service/keys/$KEY >> /root/.ssh/authorized_keys

#
# Start the ssh daemon in the foreground so that the container won't quit. 
#
/usr/sbin/sshd -D
