#!/bin/bash

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
    Cmds[3] = "cd /root;git clone https://github.com/opencore/ferry.git"
    Cmds[4] = "cd /root/ferry;python setup.py install"
    Cmds[5] = "adduser --disabled-password --gecos \"\" ferry"
    Cmds[6] = "usermod -a -G sudo ferry"
    Cmds[7] = "usermod -a -G docker ferry"
    Cmds[8] = "mkdir -p /ferry/master"
    Cmds[9] = "export FERRY_DIR=/ferry/master"
    Cmds[10] = "ferry -u install"
    Cmds[11] = "ferry server"
    Cmds[12] = "ferry pull image://ferry/heatserver"
    Cmds[13] = "rm -rf /root/ferry"

    for cmd in "${Cmds[@]}"
    do
	ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ${OS_KEY_LOCATION}/${OS_KEY}.pem -t -t ${SERVER} '${cmd}'
    done
}
