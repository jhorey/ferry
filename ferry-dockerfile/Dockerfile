FROM ubuntu:14.04

# Install Docker
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
RUN sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get --yes install lxc iptables ca-certificates cgroup-lite aufs-tools python-pip openssh-server

# Create docker group & ferry user
RUN groupadd docker
RUN adduser --disabled-password --gecos "" ferry;usermod -a -G docker ferry

RUN mkdir -p /service/sbin /var/run/sshd

# Install Ferry from GitHub master branch
WORKDIR /home/ferry
RUN git clone https://github.com/opencore/ferry
RUN cd ferry; python setup.py install

# Add the dind/start script
ADD ./make.sh /service/sbin/
RUN chmod +x /service/sbin/*