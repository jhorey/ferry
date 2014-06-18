FROM ubuntu:14.04
NAME ferry-base

# Get rid of Upstart and FUSE errors
# RUN dpkg-divert --local --rename --add /sbin/initctl && ln -s /bin/true /sbin/initctl
RUN dpkg-divert --local --add --rename --divert /bin/mknod.real /bin/mknod && ln -s /bin/true /bin/mknod

# Fake a fuse install
RUN apt-get install libfuse2
RUN cd /tmp ; apt-get download fuse
RUN cd /tmp ; dpkg-deb -x fuse_* .
RUN cd /tmp ; dpkg-deb -e fuse_*
RUN cd /tmp ; rm fuse_*.deb
RUN cd /tmp ; echo -en '#!/bin/bash\nexit 0\n' > DEBIAN/postinst
RUN cd /tmp ; dpkg-deb -b . /fuse.deb
RUN cd /tmp ; dpkg -i /fuse.deb

# Get the "mknod" command back. 
RUN rm /bin/mknod
RUN dpkg-divert --rename --remove /bin/mknod

# The previous set of commands messes up the /tmp permission for some
# reason. This just fixes it.
RUN chmod 1777 /tmp

# Make the various directories needed
RUN mkdir -p /service/keys /service/sbin /service/sconf /var/run/sshd

# Download some dependencies
RUN apt-get update;apt-get --yes install openssh-server

# Create ferry user
RUN addgroup supergroup;addgroup --gid $DOCKER docker;adduser --disabled-password --gecos "" ferry;usermod -a -G sudo ferry;usermod -a -G docker ferry;usermod -a -G supergroup ferry;chown -R ferry:docker /service;chown -R ferry:ferry /home/ferry

# Generate an ssh key for this image.
RUN ssh-keygen -f /root/.ssh/id_rsa -t rsa -N '' > /dev/null
RUN echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config;touch /etc/mtab

ADD ./setup /service/sbin/
ADD ./halt01.sh /service/sbin/
ADD ./init01.sh /service/sbin/
RUN chmod a+x /service/sbin/*
