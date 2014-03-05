#!/bin/bash

# Killing the ssh daemon should automatically exit the container,
# since the sshd is the only thing running in the foreground. 
pkill -f sshd