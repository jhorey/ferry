FROM $USER/gluster
NAME openmpi

RUN mkdir -p /service/conf /service/examples /service/packages /service/runscripts/start /service/runscripts/restart /service/runscripts/stop /service/runscripts/test

# Download the various packages needed
RUN apt-get --yes install autotools-dev autoconf automake g++ gfortran build-essential

# Add the package
RUN wget https://www.dropbox.com/s/ukfhimqxvfkic00/openmpi-1.7.3-bin.tar.gz -P /service/packages;cd /service/packages;tar -xzf openmpi-1.7.3-bin.tar.gz
RUN cd /service/packages/openmpi-1.7.3;make install
RUN ldconfig

# Make symlinks
RUN ln -s /service/packages/openmpi-1.7.3 /service/packages/openmpi

# Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./mounthelper.py /service/sbin/
ADD ./helloworld.cpp /service/examples/
ADD ./start01.sh /service/runscripts/start/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./test01.sh /service/runscripts/test/

# Create an mtab file
RUN touch /etc/mtab

# Make environment variables
RUN echo export MPI_HOME=/service/packages/openmpi >> /etc/profile
ENV MPI_HOME /service/packages/openmpi

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "listen"]