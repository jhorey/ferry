FROM $USER/cassandra
NAME titan

# Download the various packages needed
RUN apt-get --yes install unzip

# Create necessary directories
RUN mkdir -p /service/packages /service/conf/titan /service/keys /service/sbin /service/bin /service/scripts /service/ext

# Download the latest package
RUN wget $DOWNLOAD_URL/titan-all-0.3.1.zip -P /service/packages
RUN wget $DOWNLOAD_URL/rexster-server-2.3.0.zip -P /service/packages
RUN cd /service/packages/;unzip titan-all-0.3.1.zip;unzip rexster-server-2.3.0.zip

# Get rid of the tarballs. 
RUN rm /service/packages/*zip

# Make soft links
RUN ln -s /service/packages/titan-all-0.3.1 /service/packages/titan;ln -s /service/packages/rexster-server-2.3.0 /service/packages/rexster-server;ln -s /service/packages/titan-all-0.3.1/lib /service/packages/rexster-server-2.3.0/ext/titan

# Soft links to make life easier
RUN ln -s /service/packages/rexster-server-2.3.0/bin/* /usr/local/bin/
RUN ln -s /service/packages/titan-all-0.3.1/bin/* /usr/local/bin/

# Remember the various home directories
ENV REXSTER_HOME /service/packages/rexster-server-2.3.0
ENV TITAN_HOME /service/packages/titan-all-0.3.1
RUN echo export REXSTER_HOME=/service/packages/rexster-server-2.3.0 >> /etc/profile;echo export TITAN_HOME=/service/packages/titan-all-0.3.1 >> /etc/profile;echo export CLASSPATH=/service/packages/titan/lib/*: >> /etc/profile

# Add the control script to the image. 
ADD ./startnode /service/sbin/
RUN chmod a+x /service/sbin/startnode

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "init"]
