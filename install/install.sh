#!/bin/bash

# 
# Check the arguments so that we know what the user wants to do. 
# 
if [[ $# == 0 ]]; then
    # The user just wants to install Ferry on some
    # Ubuntu-based machine. 
    echo -e "Installing Ferry on ${2}@${3}..."
    echo -e "Please ensure that ${3} is running Ubuntu 14.04"

    source ferry.sh
    install_ferry "root" "localhost"
elif [[ $1 == "naked" ]]; then
    # The user just wants to install Ferry on some
    # Ubuntu-based machine. 
    echo -e "Installing Ferry on ${2}@${3}..."
    echo -e "Please ensure that ${3} is running Ubuntu 14.04"

    source ferry.sh
    install_ferry $2 $3
elif [[ $2 == "openstack" ]]; then
    echo -e "Installing Ferry on OpenStack..."

    source openstack.sh
    install_on_openstack
fi
