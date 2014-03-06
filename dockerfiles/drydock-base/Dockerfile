FROM base
NAME drydock-base

# This is so that we don't get Upstart error messages
# (specific to running Ubuntu in chroot environment)
RUN dpkg-divert --local --rename --add /sbin/initctl;ln -s /bin/true /sbin/initctl

# Make the various directories needed
RUN mkdir -p /service/keys /var/run/sshd

# Download some dependencies
RUN apt-get update;apt-get --yes install openssh-server

# Create drydock user
RUN addgroup supergroup;addgroup --gid $DOCKER docker;adduser --disabled-password --gecos "" drydock;usermod -a -G sudo drydock;usermod -a -G docker drydock;usermod -a -G supergroup drydock;chown -R drydock:docker /service;chown -R drydock:drydock /home/drydock

# Generate an ssh key for this image.
RUN ssh-keygen -f /root/.ssh/id_rsa -t rsa -N '' > /dev/null

# Add the public ssh key of the current workstation to the
# authorized list so that it is easy to interact with the deploy image.
ADD ./id_rsa.pub /service/keys/
RUN cp /service/keys/id_rsa.pub /root/.ssh/
RUN cat /service/keys/id_rsa.pub >> /root/.ssh/authorized_keys;echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config;touch /etc/mtab