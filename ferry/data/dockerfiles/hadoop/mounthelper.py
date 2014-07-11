import json
import os
import sys
import logging
from subprocess import Popen, PIPE

def mkdir(directory):
    if not os.path.isdir(directory):
        cmd = 'mkdir -p %s' % directory
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        logging.info(cmd)
        logging.info(output)

def mount(entry_point, mount_point):
    # Check if the mount point exists. If not
    # go ahead and create it. 
    # mount -t glusterfs entry_point mount_point
    cmd = 'mount -t glusterfs %s %s' % (entry_point,
                                        mount_point)
    output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
    logging.info(cmd)
    logging.info(output)

def umount(mount_point):
    cmd = 'cat /etc/mtab | grep /service/data | awk \'{print $2}\''
    output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
    if output.strip() != "":
        cmd = 'umount %s' % mount_point
        output = Popen(cmd, stdout=PIPE, shell=True).stdout.read()
        logging.info(cmd)
        logging.info(output)

cmd = sys.argv[1]
if cmd == "mount":
    entry = sys.argv[2]
    mkdir('/service/data')
    mount(entry, '/service/data')
elif cmd == "umount":
    umount('/service/data')
