#!/bin/bash

# Bash colors
RED='\e[0;31m'
GREEN='\e[0;32m'
ORANGE='\e[0;33m'
BLUE='\e[0;34m'
NC='\e[0m'

VERSION='0.3.3.3'

# Helper to build the Ferry image. 
function make_ferry_image {
    OUTPUT=$(docker inspect ferry/ferry-server | grep "\[")
    if [[ $OUTPUT == "[]" ]]; then
    	echo -e "${GREEN}pulling the ferry image${NC}"
    	docker pull ferry/ferry-server
    else
    	echo -e "${BLUE}found ferry image, proceeding${NC}"
    fi
}

# Build all the images. Assumed that it is being 
# called from externally. 
function make_images_external {
    # Check if the 'ferry' image is actually built. If not
    # go ahead and build the image. 
    make_ferry_image

    # Now go ahead and run the ferry server. 
    if [ -z "$FERRY_DIR" ]; then
    	echo -e "${RED}you must set the FERRY_DIR environment variable${NC}"
    else
    	echo -e "${BLUE}starting ferry, using $FERRY_DIR to save state${NC}"
	docker run --privileged -v $FERRY_DIR:/var/lib/ferry -e FERRY_SCRATCH=/var/lib/ferry/scratch -e USER=$USER -e HOME=/var/lib/ferry -e FERRY_HOME=/usr/local/lib/python2.7/dist-packages/ferry -i -t ferry/ferry-server /service/sbin/make.sh internal $1
    fi
}

# Function to connect to the Ferry image. 
function run_ferry_server {
    # Check if the 'ferry' image is actually built. If not
    # go ahead and build the image. 
    make_ferry_image

    if [ -z "$FERRY_DIR" ]; then
    	echo -e "${RED}you must set the FERRY_DIR environment variable${NC}"
    else
    	echo -e "${BLUE}starting ferry client${NC}"
	docker run --privileged -v $FERRY_DIR:/var/lib/ferry -e FERRY_SCRATCH=/var/lib/ferry/scratch -e USER=$USER -e HOME=/var/lib/ferry -e FERRY_HOME=/usr/local/lib/python2.7/dist-packages/ferry -i -t ferry/ferry-server /service/sbin/make.sh console
    fi
}

#
# Authorize the public key for password-less ssh. 
#
function authorize_keys {
    cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
}

#
# Start an SSH server. 
#
function start_ssh {
    /usr/sbin/sshd -D
}

# Display the usage information. 
if [ "$#" == 0 ]; then
    echo "Usage: ferry-dust CMD"
    echo ""
    echo "Commands:"
    echo "    install  Install all the Ferry images"
    echo "    start    Log into the Ferry client"
    echo ""
    exit 1
fi 

# Parse any options. 
ARG=""
if [ "$#" == 2 ]; then
    ARG=$2
fi

# Ok parse the user arguments. 
if [[ $1 == "start" ]]; then
    run_ferry_server
elif [[ $1 == "install" ]]; then
    make_images_external $ARG
fi
