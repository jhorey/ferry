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
ADD ./stop10.sh /service/runscripts/stop/
ADD ./test01.sh /service/runscripts/test/

# Download the latest package
RUN wget https://www.dropbox.com/s/fwr26lj0s7nu0aw/rexster-console-2.3.0.zip -P /service/packages;cd /service/packages/;unzip rexster-console-2.3.0.zip

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "listen"]
