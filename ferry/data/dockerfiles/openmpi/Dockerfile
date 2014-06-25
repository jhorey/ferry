FROM $USER/gluster
NAME openmpi

RUN mkdir -p /service/examples /service/packages /service/runscripts/start /service/runscripts/restart /service/runscripts/stop /service/runscripts/test

# Download the various packages needed
RUN apt-get --yes install autotools-dev autoconf automake g++ gfortran build-essential libevent-dev 

# Add the package
RUN wget $DOWNLOAD_URL/openmpi-1.8.1-bin.tar.gz -P /service/packages
RUN cd /service/packages;tar -xzf openmpi-1.8.1-bin.tar.gz
RUN cd /service/packages/openmpi-1.8.1;make install
RUN ldconfig

# Get rid of the tarballs.
RUN rm /service/packages/*.tar.gz

# Make symlinks
RUN ln -s /service/packages/openmpi-1.8.1 /service/packages/openmpi
RUN ln -s /usr/local/etc /service/conf/openmpi

# Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./mounthelper.py /service/sbin/
ADD ./start01.sh /service/runscripts/start/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./restart01.sh /service/runscripts/restart/
RUN chmod a+x /service/sbin/startnode;chmod a+x /service/runscripts/start/*;chmod a+x /service/runscripts/stop/*;chmod a+x /service/runscripts/restart/*

# Make environment variables
RUN echo export MPI_HOME=/service/packages/openmpi >> /etc/profile
RUN echo export MPI_CONF=/service/conf/openmpi >> /etc/profile

# Generate an ssh key for this image.
RUN mkdir /home/ferry/.ssh;ssh-keygen -f /home/ferry/.ssh/id_rsa -t rsa -N '' > /dev/null
RUN cat /home/ferry/.ssh/id_rsa.pub >> /home/ferry/.ssh/authorized_keys;echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config;touch /etc/mtab
RUN chown -R ferry:ferry /home/ferry/.ssh

