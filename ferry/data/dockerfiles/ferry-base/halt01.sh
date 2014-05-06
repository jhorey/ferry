#! /bin/bash

# 
# This the halt script used by all the Ferry images. The halt script is the
# last thing executed by the container before it is stopped. This script should
# not be modified by the container. 
# 
# Currently this script just stops the SSH daemon. 
# 
    
pkill -f sshd