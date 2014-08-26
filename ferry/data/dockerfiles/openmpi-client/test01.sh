#!/bin/bash

source /etc/profile

# Bash colors
GREEN='\e[0;32m'
NC='\e[0m'

# Commands
MKBINS='mkdir /service/data/binaries'
MKOUT='mkdir /service/data/outputs'
COMPILE='mpic++ -W -Wall /service/examples/helloworld.cpp -o /service/data/binaries/helloworld.o'
RUN='mpirun -np 4 --hostfile $MPI_CONF/hosts /service/data/binaries/helloworld.o >> /service/data/outputs/mpitest.out'

function run_as_ferry {
    echo -e "${GREEN} ${2} ${NC}"
    if [ $USER == "root" ]; then
	su ferry -c "$1"
    else
	$1
    fi
}

run_as_ferry "$MKBINS" "Creating binary directory"
run_as_ferry "$MKOUT" "Creating output directory"
run_as_ferry "$COMPILE" "Compiling MPI application"
run_as_ferry "$RUN" "Running MPI application"
