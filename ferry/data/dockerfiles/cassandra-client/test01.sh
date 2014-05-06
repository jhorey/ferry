#!/bin/bash

source /etc/profile

# Bash colors
GREEN='\e[0;32m'
NC='\e[0m'

function run_as_ferry {
    echo -e "${GREEN} ${2} ${NC}"
    if [ $USER == "root" ]; then
	su ferry -c "$1"
    else
	$1
    fi
}

if [ $1 == "cql" ]; then
    CMD='/service/bin/cqlsh -f /service/scripts/testusers.db'
    run_as_ferry "$CMD" "Running CQL example"
elif [ $1 == "natural" ]; then
    CMD='/service/packages/titan/bin/gremlin.sh -e /service/scripts/naturalgraph.groovy'
    run_as_ferry "$CMD" "Running Titan example"
elif [ $1 == "gods" ]; then
    CMD='/service/packages/titan/bin/gremlin.sh -e /service/scripts/loadgods.groovy'
    run_as_ferry "$CMD" "Running Titan example"
fi