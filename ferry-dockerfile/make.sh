#!/bin/bash

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
		    echo "Could not make a tmpfs mount. Did you use -privileged?"
		    exit 1
	    }

    if [ -d /sys/kernel/security ] && ! mountpoint -q /sys/kernel/security
    then
	mount -t securityfs none /sys/kernel/security || {
            echo "Could not mount /sys/kernel/security."
            echo "AppArmor detection and -privileged mode might break."
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
    	    echo "WARNING: the 'devices' cgroup should be in its own hierarchy."
    grep -qw devices /proc/1/cgroup ||
	    echo "WARNING: it looks like the 'devices' cgroup is not mounted."

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
    ferry install -u
}

function make_ferry_image {
    OUTPUT=$(docker inspect ferry/ferry-server | grep "\[")
    if [ $OUTPUT == "[]" ]; then
    	echo "building the ferry image"
    	docker build --rm=true -t ferry/ferry-server .
    else
    	echo "found ferry image, proceeding"
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
    	echo "you must set the FERRY_DIR environment variable"
    else
    	echo "starting ferry, using $FERRY_DIR to save state"
	docker run --privileged -v $FERRY_DIR:/var/lib/ferry -e FERRY_SCRATCH=/var/lib/ferry/scratch -e HOME=/var/lib/ferry -e FERRY_HOME=/usr/local/lib/python2.7/dist-packages/ferry-0.1.21-py2.7.egg/ferry -i -t ferry/ferry-server /service/sbin/make.sh internal
    fi
}

# Function to connect to the Ferry image. 
function run_ferry_server {
    # Check if the 'ferry' image is actually built. If not
    # go ahead and build the image. 
    make_ferry_image

    if [ -z "$FERRY_DIR" ]; then
    	echo "you must set the FERRY_DIR environment variable"
    else
    	echo "starting ferry client"
	docker run --privileged -v $FERRY_DIR:/var/lib/ferry -e FERRY_SCRATCH=/var/lib/ferry/scratch -e HOME=/var/lib/ferry -e FERRY_HOME=/usr/local/lib/python2.7/dist-packages/ferry-0.1.21-py2.7.egg/ferry -i -t ferry/ferry-server /service/sbin/make.sh console
    fi
}

# Check what version of Docker is running. Since we're running Docker in Docker,
# we need at least version 0.6.0. 
function check_docker_version {
    MINVERSION="0.6.0"
    VERSION=$(docker version | grep Server | awk '{print $3}')
    vercomp $VERSION $MINVERSION
    case $? in
	2) echo "Docker version >= $MINVERSION required, found $VERSION" 
	    exit 1
	    ;;
	*) echo "Docker version $VERSION accepted" ;;
    esac
}

function check_ghost_mongo {
    ferry clean
}

# Ok parse the user arguments. 
if [ $1 == "internal" ] 
then
    prepare_dind
    make_images_internal
elif [ $1 == "console" ] 
then
    prepare_dind
    check_ghost_mongo
    exec bash
elif [ $1 == "install" ] 
then
    check_docker_version
    make_images_external
elif [ $1 == "start" ] 
then
    check_docker_version
    run_ferry_server
fi    