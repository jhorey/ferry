#!/bin/bash

su drydock -c 'mkdir /service/data/binaries'
su drydock -c 'mpic++ -W -Wall /service/examples/helloworld.cpp -o /service/data/binaries/helloworld.o'
su drydock -c 'mpirun -np 4 --hostfile /usr/local/etc/instances /service/data/binaries/helloworld.o'
