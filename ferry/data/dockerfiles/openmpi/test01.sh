#!/bin/bash

su ferry -c 'mkdir /service/data/binaries'
su ferry -c 'mpic++ -W -Wall /service/examples/helloworld.cpp -o /service/data/binaries/helloworld.o'
su ferry -c 'mpirun -np 4 --hostfile /usr/local/etc/instances /service/data/binaries/helloworld.o'
