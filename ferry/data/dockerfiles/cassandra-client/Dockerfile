FROM $USER/titan
NAME cassandra-client

# Download the various packages needed
RUN apt-get --yes install git maven

# Create necessary directories
RUN mkdir -p /service/runscripts/start /service/runscripts/stop /service/runscripts/restart /service/runscripts/test

# Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./testusers.db /service/scripts/
ADD ./gods.json /service/scripts/
ADD ./naturalgraph.groovy /service/scripts/
ADD ./loadgods.groovy /service/scripts/
ADD ./rexexample.sh /service/scripts/

# Add our runscripts
ADD ./start01.sh /service/runscripts/start/
ADD ./restart01.sh /service/runscripts/restart/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./test01.sh /service/runscripts/test/
RUN chmod a+x /service/sbin/startnode;chmod a+x /service/runscripts/start/*;chmod a+x /service/runscripts/stop/*;chmod a+x /service/runscripts/test/*;chmod a+x /service/runscripts/restart/*;chmod a+x /service/scripts/rexexample.sh

# Download the latest package
RUN wget $DOWNLOAD_URL/rexster-console-2.3.0.zip -P /service/packages
RUN cd /service/packages/;unzip rexster-console-2.3.0.zip

# Get rid of the tarballs.
RUN rm /service/packages/*zip
RUN rm -rf /var/cache/apt/archives/*
RUN rm -rf /var/lib/apt/lists/*