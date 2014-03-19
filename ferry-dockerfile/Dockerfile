FROM ubuntu:13.10

# Install Docker
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
RUN sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"
RUN apt-get update;apt-get --yes install iptables ca-certificates lxc lxc-docker-0.8.1 python-pip openssh-server

# Create ferry user
RUN adduser --disabled-password --gecos "" ferry;usermod -a -G docker ferry

# Generate an ssh key for the Ferry images.
RUN mkdir -p /service/keys /service/sbin /var/run/sshd
RUN ssh-keygen -f /service/keys/id_rsa -t rsa -N '' > /dev/null

# Create another key for this image. 
RUN ssh-keygen -f /root/.ssh/id_rsa -t rsa -N '' > /dev/null

# Install Ferry
# RUN pip install ferry
ADD ./foo /service/packages/
RUN cd /service/packages/;python setup.py install
ADD ./make.sh /service/sbin/
RUN chmod +x /service/sbin/*