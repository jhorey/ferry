#!/bin/bash

cat /service/conf/cassandra/servers >> /etc/hosts
echo export CQLSH_HOST=$1 >> /etc/profile
source /etc/profile
