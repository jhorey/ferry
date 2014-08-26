#!/bin/bash

# 
# Generate some configuration files. 
# 

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
}

function print_net_info {
    echo ""    
    echo "Networks:"
    neutron --os-url $1 net-list 2> /dev/null

    echo ""
    echo "Routers:"
    neutron --os-url $1 router-list 2> /dev/null
}

if [[ $1 == "hp" ]]; then
    # Make sure that the user has supplied some OpenStack credentials. 
    check_openstack_credentials

    # Now find out the list of servers, etc. 
    echo "====US West===="
    print_net_info "https://region-a.geo-1.network.hpcloudsvc.com"

    echo ""
    echo "====US East===="
    print_net_info "https://region-b.geo-1.network.hpcloudsvc.com"
fi
