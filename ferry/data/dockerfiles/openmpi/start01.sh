#!/bin/bash

# Mount GlusterFS and set the owner as 'drydock' user. 
python /service/sbin/mounthelper.py mount $1
chown -R drydock:docker /service/data