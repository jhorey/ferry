#!/bin/bash

#
# Create the Ferry base image
# The script performs the following:
# (0) Download an Ubuntu 14.04 image and upload to OpenStack
# (1) Create a new instance from some base image (Ubuntu 14.04)
# (2) Save the instance
# 

#
# OpenStack credentials
# 
OS_AUTH_URL=https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/
OS_NO_CLIENT_AUTH=1
OS_REGION_NAME=region-a.geo-1
OS_TENANT_ID=10089763026941
OS_TENANT_NAME=10937347415536-Project
OS_URL=https://region-a.geo-1.network.hpcloudsvc.com
OS_USERNAME=jhorey

#
# Base image should be an Ubuntu 14.04 image
# 
# BASE_IMAGE="Ubuntu Server 14.04.1 LTS (amd64 20140724) - Partner Image"
UBUNTU_USER="ubuntu"
OS_FLAVOR="standard.xsmall"
OS_KEY="ferry-test"
OS_PRIVATE_KEY="/ferry/keys/ferry-test.pem"
OS_SEC="default"
EXT_NET="122c72de-0924-4b9f-8cf3-b18d5d3d292c"

#
# Ferry configuration
#
FERRY_INSTANCE="ferry-base"
FERRY_IMAGE="ferry-base-image"

#
# Global vars
#
FLOATING_IP="127.0.0.1"

function start_ubuntu_image {
    # 
    # Start the base image and attach a floating IP so that
    # we can interact with it.
    #
    nova boot --flavor "${OS_FLAVOR}" --image "${BASE_IMAGE}" --key-name "${OS_KEY_NAME}" --security-groups "${OS_SEC}" $FERRY_INSTANCE

    # Wait for the instance to boot up
    STATUS=""
    while [[ $STATUS != "ACTIVE" ]]; do
	STATUS=$(nova show --minimal $FERRY_INSTANCE | grep status | awk '{print $4}')
	sleep 2
    done

    # Create a floating IP and then associate the instance with it. 
    FLOATING_IP=$(neutron floatingip-create $EXT_NET -f value | sed -n 3p )
    nova floating-ip-associate $FERRY_INSTANCE $FLOATING_IP
}

function install_ferry {
    #
    # Install Ferry on the remote instance. 
    #
    USER=$1
    SERVER=$2

    # Cmds to run. 
    Cmds[0] = "apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9"
    Cmds[1] = "sh -c \"echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list\""
    Cmds[2] = "apt-get --yes install xfsprogs python-pip python-dev git lxc-docker-0.8.1"
    Cmds[3] = "cd /home/${USER};git clone https://github.com/opencore/ferry.git"
    Cmds[4] = "cd /home/${USER}/ferry;python setup.py install"
    Cmds[5] = "adduser --disabled-password --gecos \"\" ferry"
    Cmds[6] = "usermod -a -G sudo ferry"
    Cmds[7] = "usermod -a -G docker ferry"
    Cmds[8] = "mkdir -p /ferry/master"
    Cmds[9] = "export FERRY_DIR=/ferry/master"
    Cmds[10] = "ferry -u install"
    Cmds[11] = "rm -rf /home/${USER}/ferry"

    for cmd in "${Cmds[@]}"
    do
	SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${OS_KEY_LOCATION}/${OS_KEY}.pem -t -t ${SERVER} '${cmd}'"
    done
}

function save_ferry_image {
    #
    # Save the running instance as a new image. 
    #
    nova image-create $FERRY_INSTANCE $FERRY_IMAGE
}

function import_ubuntu_image {
    # 
    # Download and import a base Ubuntu image
    # into the OpenStack cluster. 
    #

    # First need to download the Ubuntu 14.04 image and
    # untar it so that we can get to the image.
    wget https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box
    tar xzf trusty-server-cloudimg-amd64-vagrant-disk1.box

    # Now upload to Glance. 
    
}

function check_openstack_credentials {
    #
    # Check if the user has specified the various OpenStack credentials
    # 
    : ${OS_USERNAME?"Please set OS_USERNAME to your username"}
    : ${OS_PASSWORD?"Please set OS_PASSWORD to your password"}
    : ${OS_TENANT_ID?"Please set OS_TENANT_ID to your tenant ID"}
    : ${OS_TENANT_NAME?"Please set OS_TENANT_NAME to your tenant name"}
    : ${OS_AUTH_URL?"Please set OS_AUTH_URL to the Keystone URL"}
    : ${OS_REGION_NAME?"Please set OS_REGION_NAME to the OpenStack region"}
    : ${OS_FLAVOR?"Please set OS_FLAVOR to the default flavor name (e.g., standard.xsmall)"}
    : ${OS_KEY_NAME?"Pleas set OS_KEY_NAME to the name of the ssh key (e.g., my-key)"}
    : ${OS_KEY_LOCATION?"Please set OS_KEY_LOCATION to the location of the private key"}
    : ${OS_SEC?"Please set OS_SEC to your default security group"}
    : ${OS_EXT_NET?"Please set OS_EXT_NET to the ID of your external network"}
}

# 
# Check the arguments so that we know what the user wants to do. 
# 
if [[ $1 == "naked" ]]; then
    # The user just wants to install Ferry on some
    # Ubuntu-based machine. 
    echo -e "Installing Ferry on ${2}@${3}..."
    echo -e "Please ensure that ${3} is running Ubuntu 14.04"

    install_ferry $2 $3
elif [[ $2 == "openstack" ]]; then
    # Check for OpenStack credentials
    check_openstack_credentials

    # We need to check if the user has specified
    # a base Ubuntu image. If not, we need to import one. 
    if [[ -z $UBUNTU_IMAGE ]]; then
	import_ubuntu_image
    fi

    # Now instantiate a new Ubuntu instance and associate
    # a floating IP with that instance. 
    start_ubuntu_image

    # Now we'll need to install Ferry on that instance.
    install_ferry $UBUNTU_USER $FLOATING_IP

    # Finally save the new Ferry image. 
    echo -e "saving ferry image"
    save_ferry_image
fi
