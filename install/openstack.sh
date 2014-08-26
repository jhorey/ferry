#!/bin/bash

UBUNTU_USER="ubuntu"
UBUNTU_IMAGE_NAME="Ubuntu Server 14.04 (amd64) - Ferry Image"

#
# Ferry configuration
#
FERRY_INSTANCE="Ferry"
FERRY_IMAGE="Ferry Server"

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

    if [[ -z $UBUNTU_IMAGE ]]; then
	echo -e "Ubuntu image not found. Importing..."

	# First need to download the Ubuntu 14.04 image and
	# untar it so that we can get to the image.
	wget https://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img

	# Now upload to Glance. 
	glance image-create --name $UBUNTU_IMAGE_NAME --disk-format=raw --container-format=bare --file=./trusty-server-cloudimg-amd64-disk1.img
    fi
}

function install_on_openstack {
    # Include the basic Ferry installation functions. 
    source ferry.sh

    # Check for OpenStack credentials
    echo -e "Checking OpenStack credentials"
    check_openstack_credentials

    # We need to check if the user has specified
    # a base Ubuntu image. If not, we need to import one. 
    echo -e "Checking for Ubuntu image"
    import_ubuntu_image

    # Now instantiate a new Ubuntu instance and associate
    # a floating IP with that instance. 
    echo -e "Starting Ubuntu instance"
    start_ubuntu_image

    # Now we'll need to install Ferry on that instance.
    echo -e "Installing Ferry"
    install_ferry $UBUNTU_USER $FLOATING_IP

    # Finally save the new Ferry image. 
    echo -e "Saving Ferry image"
    save_ferry_image
}
