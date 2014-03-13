#!/bin/bash

# Mount GlusterFS and set the owner as 'ferry' user. 
python /service/sbin/mounthelper.py mount $1
chown -R ferry:docker /service/data