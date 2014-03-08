#!/bin/bash

cat /service/conf/servers >> /etc/hosts
echo export CQLSH_HOST=$1 >> /etc/profile
source /etc/profile