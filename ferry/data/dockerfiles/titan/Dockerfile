FROM $USER/cassandra
NAME titan

# Download the various packages needed
RUN apt-get --yes install unzip

# Create necessary directories
RUN mkdir -p /service/packages /service/conf /service/keys /service/sbin /service/bin /service/scripts /service/ext

# Download the latest package
RUN https://www.dropbox.com/s/q5g3x6yr2dftpxl/titan-all-0.3.1.zip -P /service/packages;wget https://www.dropbox.com/s/yzaynzpoooui1f1/rexster-server-2.3.0.zip -P /service/packages;cd /service/packages/;unzip titan-all-0.3.1.zip;cd /service/packages/;unzip rexster-server-2.3.0.zip

# Make soft links
RUN ln -s /service/packages/titan-all-0.3.1 /service/packages/titan;ln -s /service/packages/rexster-server-2.3.0 /service/packages/rexster-server;ln -s /service/packages/titan-all-0.3.1/lib /service/packages/rexster-server-2.3.0/ext/titan

# Remember the various home directories
RUN echo export REXSTER_HOME=/service/packages/rexster-server-2.3.0 >> /etc/profile;echo export TITAN_HOME=/service/packages/titan-all-0.3.1 >> /etc/profile;echo export CLASSPATH=/service/packages/titan/lib/*: >> /etc/profile

# Add the control script to the image. 
ADD ./startnode /service/sbin/

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "listen"]
