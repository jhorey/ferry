import json
import os
import sys
import logging
from subprocess import Popen, PIPE

def mount(entry_point, mount_point):
    # Check if the mount point exists. If not
    # go ahead and create it. 
    cmd = 'mount -t glusterfs %s %s' % (entry_point,
                                        mount_point)
    output = Popen(cmd, stdout=PIPE,shell=True).stdout.read()
    logging.warning(output)

def umount(mount_point):
    cmd = 'cat /etc/mtab | grep /service/data | awk \'{print $2}\''
    output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
    if output.strip() != "":
        cmd = 'umount %s' % mount_point
        Popen(cmd, shell=True)

cmd = sys.argv[1]
if cmd == "mount":
    entry = sys.argv[2]
    mount(entry, '/service/data')
elif cmd == "umount":
    umount('/service/data')
