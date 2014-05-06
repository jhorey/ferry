#! /bin/bash

# 
# This the initialization script used by all the Ferry images. The init script is the
# first script run after the container is started. This script should not be modified 
# by the container. 
# 
# 
# Currently the script is very simple. It creates the FUSE device (necessary for
# older versions of Docker) and sets up an SSH daemon. This allows the host to
# communicate with the container. 
#

source /service/sbin/setup

create_fuse_dev    
cat /service/keys/id_rsa.pub >> /root/.ssh/authorized_keys
/usr/sbin/sshd -D