import json
import os
import sys
import logging
from subprocess import Popen, PIPE

def mkdir(directory):
    if not os.path.isdir(directory):
        cmd = 'mkdir -p %s' % directory
        Popen(cmd, shell=True)

def mount(entry_point, mount_point):
    # Check if the mount point exists. If not
    # go ahead and create it. 
    # mount -t glusterfs entry_point mount_point
    cmd = 'mount -t glusterfs %s %s' % (entry_point,
                                        mount_point)
    Popen(cmd, shell=True)

def umount(mount_point):
    cmd = 'umount %s' % mount_point
    Popen(cmd, shell=True)

cmd = sys.argv[1]
if cmd == "mount":
    entry = sys.argv[2]
    mkdir('/service/data')
    mount(entry, '/service/data')
elif cmd == "umount":
    umount('/service/data')
