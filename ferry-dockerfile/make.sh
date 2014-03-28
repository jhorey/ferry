#!/bin/bash

# Bash colors
RED='\e[0;31m'
GREEN='\e[0;32m'
ORANGE='\e[0;33m'
BLUE='\e[0;34m'
NC='\e[0m'

# Compare two version numbers. 
function vercomp () {
    if [[ $1 == $2 ]]
    then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    # fill empty fields in ver1 with zeros
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++))
    do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++))
    do
        if [[ -z ${ver2[i]} ]]
        then
            # fill empty fields in ver2 with zeros
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]}))
        then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]}))
        then
            return 2
        fi
    done
    return 0
}

# Prepare the docker environment for docker-in-docker. This code is from
# jpetazzo/dind
function prepare_dind {
    # First, make sure that cgroups are mounted correctly.
    CGROUP=/sys/fs/cgroup

    [ -d $CGROUP ] || 
            mkdir $CGROUP

    mountpoint -q $CGROUP || 
            mount -n -t tmpfs -o uid=0,gid=0,mode=0755 cgroup $CGROUP || {
		    echo -e "${RED}Could not make a tmpfs mount. Did you use -privileged?${NC}"
		    exit 1
	    }

    if [ -d /sys/kernel/security ] && ! mountpoint -q /sys/kernel/security
    then
	mount -t securityfs none /sys/kernel/security || {
            echo -e "${RED}Could not mount /sys/kernel/security.${NC}"
            echo -e "${RED}AppArmor detection and -privileged mode might break.${NC}"
	}
    fi

    # Mount the cgroup hierarchies exactly as they are in the parent system.
    for SUBSYS in $(cut -d: -f2 /proc/1/cgroup)
    do
	    [ -d $CGROUP/$SUBSYS ] || mkdir $CGROUP/$SUBSYS
            mountpoint -q $CGROUP/$SUBSYS || 
                    mount -n -t cgroup -o $SUBSYS cgroup $CGROUP/$SUBSYS

            # The two following sections address a bug which manifests itself
            # by a cryptic "lxc-start: no ns_cgroup option specified" when
            # trying to start containers withina container.
            # The bug seems to appear when the cgroup hierarchies are not
            # mounted on the exact same directories in the host, and in the
            # container.

            # Named, control-less cgroups are mounted with "-o name=foo"
            # (and appear as such under /proc/<pid>/cgroup) but are usually
            # mounted on a directory named "foo" (without the "name=" prefix).
            # Systemd and OpenRC (and possibly others) both create such a
            # cgroup. To avoid the aforementioned bug, we symlink "foo" to
            # "name=foo". This shouldn't have any adverse effect.
            echo $SUBSYS | grep -q ^name= && {
                    NAME=$(echo $SUBSYS | sed s/^name=//)
                    ln -s $SUBSYS $CGROUP/$NAME
            }

            # Likewise, on at least one system, it has been reported that
            # systemd would mount the CPU and CPU accounting controllers
            # (respectively "cpu" and "cpuacct") with "-o cpuacct,cpu"
            # but on a directory called "cpu,cpuacct" (note the inversion
            # in the order of the groups). This tries to work around it.
            [ $SUBSYS = cpuacct,cpu ] && ln -s $SUBSYS $CGROUP/cpu,cpuacct
    done

    # Note: as I write those lines, the LXC userland tools cannot setup
    # a "sub-container" properly if the "devices" cgroup is not in its
    # own hierarchy. Let's detect this and issue a warning.
    grep -q :devices: /proc/1/cgroup ||
    	    echo -e "${ORANGE}WARNING: the 'devices' cgroup should be in its own hierarchy.${NC}"
    grep -qw devices /proc/1/cgroup ||
	    echo -e "${ORANGE}WARNING: it looks like the 'devices' cgroup is not mounted.${NC}"

    # Now, close extraneous file descriptors.
    pushd /proc/self/fd >/dev/null
    for FD in *
    do
	    case "$FD" in
	    # Keep stdin/stdout/stderr
	    [012])
		    ;;
	    # Nuke everything else
	    *)
		    eval exec "$FD>&-"
		    ;;
	    esac
    done
    popd >/dev/null

    # If a pidfile is still around (for example after a container restart),
    # delete it so that docker can start.
    rm -rf /var/run/ferry.pid
}

# Build all the images. Assumed that it is being
# called from internally. 
function make_images_internal {
    OUTPUT=$(ferry install $1)
    echo -e "${GREEN}${OUTPUT}${NC}"
}

# Helper to build the Ferry image. 
function make_ferry_image {
    OUTPUT=$(docker inspect ferry/ferry-server | grep "\[")
    if [[ $OUTPUT == "[]" ]] || [[ $1 == "-u" ]] || [[ $1 == "-f" ]]; then
	if [[ $1 == "-f" ]]; then
    	    echo -e "${GREEN}building the ferry image${NC}"
    	    docker build --rm=true --no-cache=true -t ferry/ferry-server .
	else
    	    echo -e "${GREEN}pulling the ferry image${NC}"
    	    docker pull ferry/ferry-server
	fi
    else
    	echo -e "${BLUE}found ferry image, proceeding${NC}"
    fi
}

# Build all the images. Assumed that it is being 
# called from externally. 
function make_images_external {
    # Check if the 'ferry' image is actually built. If not
    # go ahead and build the image. 
    make_ferry_image $1

    # Now go ahead and run the ferry server. 
    if [ -z "$FERRY_DIR" ]; then
    	echo -e "${RED}you must set the FERRY_DIR environment variable${NC}"
    else
    	echo -e "${BLUE}starting ferry, using $FERRY_DIR to save state${NC}"
	docker run --privileged -v $FERRY_DIR:/var/lib/ferry -e FERRY_SCRATCH=/var/lib/ferry/scratch -e HOME=/var/lib/ferry -e FERRY_HOME=/usr/local/lib/python2.7/dist-packages/ferry -i -t ferry/ferry-server /service/sbin/make.sh internal $1
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
	docker run --privileged -v $FERRY_DIR:/var/lib/ferry -e FERRY_SCRATCH=/var/lib/ferry/scratch -e HOME=/var/lib/ferry -e FERRY_HOME=/usr/local/lib/python2.7/dist-packages/ferry -i -t ferry/ferry-server /service/sbin/make.sh console
    fi
}

# Check what version of Docker is running. Since we're running Docker in Docker,
# we need at least version 0.6.0. 
function check_docker_version {
    MINVERSION="0.6.0"
    VERSION=$(docker version | grep Server | awk '{print $3}')
    vercomp $VERSION $MINVERSION
    case $? in
	2) echo -e "${RED}Docker version >= $MINVERSION required, found $VERSION${NC}" 
	    exit 1
	    ;;
	*) echo -e "${GREEN}Docker version $VERSION accepted${NC}" ;;
    esac
}

# Check if the user has quit the external docker container
# without shutting down Ferry properly. 
function check_ghost_mongo {
    OUTPUT=$(ferry clean)
    echo -e "${GREEN}${OUTPUT}${NC}"
}

# Display the usage information. 
if [ "$#" == 0 ]; then
    echo "Usage: make.sh CMD <OPTIONS>"
    echo ""
    echo "Options:"
    echo "    -u       Force upgrade"
    echo "    -f       Build Ferry server image"
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
if [[ $1 == "internal" ]]; then
    prepare_dind
    make_images_internal $ARG
elif [[ $1 == "console" ]]; then
    prepare_dind
    check_ghost_mongo
    exec bash
elif [[ $1 == "install" ]]; then
    check_docker_version
    make_images_external $ARG
elif [[ $1 == "start" ]]; then
    check_docker_version
    run_ferry_server
fi    