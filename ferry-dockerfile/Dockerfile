FROM ubuntu:14.04

# Install Docker
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
RUN sh -c "echo deb http://get.docker.io/ubuntu docker main > /etc/apt/sources.list.d/docker.list"

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get --yes upgrade
RUN DEBIAN_FRONTEND=noninteractive apt-get --yes install lxc lxc-docker iptables ca-certificates cgroup-lite aufs-tools build-essential python-dev python-pip python-babel openssh-server

# Create docker group & ferry user
# RUN groupadd docker
RUN adduser --disabled-password --gecos "" ferry;usermod -a -G docker ferry

RUN mkdir -p /service/sbin /var/run/sshd

# Install Ferry from GitHub master branch
WORKDIR /home/ferry
RUN pip install ferry

# Add the dind/start script
ADD ./make.sh /service/sbin/
RUN chmod +x /service/sbin/*

# Add customized ssh banner 
RUN rm /etc/update-motd.d/*
RUN rm /var/run/motd.dynamic
ADD ./50-ferryheader /etc/update-motd.d/
ADD ./51-ferryhelp /etc/update-motd.d/
RUN chmod +x /etc/update-motd.d/50-ferryheader
RUN chmod +x /etc/update-motd.d/51-ferryhelp
RUN /etc/update-motd.d/50-ferryheader >> /var/run/motd.dynamic
RUN /etc/update-motd.d/51-ferryhelp >> /var/run/motd.dynamic