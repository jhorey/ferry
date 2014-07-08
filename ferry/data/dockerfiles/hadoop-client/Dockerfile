FROM $USER/hadoop-base
NAME hadoop-client

# Make the various directories needed
RUN mkdir -p /service/runscripts/start /service/runscripts/restart /service/runscripts/test /service/runscripts/stop

# The Pig package should just reside on the client.
RUN wget $DOWNLOAD_URL/pig-0.12.1.tar.gz -P /service/packages
RUN cd /service/packages;tar -xzf pig-0.12.1.tar.gz

# Create a symlink to the package dir. 
RUN ln -s /service/packages/pig-0.12.1 /service/packages/pig;

# Environment variables. 
ENV PIG_HOME /service/packages/pig
ENV PIG_CLASSPATH /service/conf/hadoop
RUN echo export PIG_HOME=/service/packages/pig >> /etc/profile;echo export PIG_CLASSPATH=/service/conf/hadoop >> /etc/profile;

# Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./createtable.sql /service/scripts/
ADD ./count.pig /service/scripts/
ADD ./mounthelper.py /service/scripts/
ADD ./start01.sh /service/runscripts/start/
ADD ./restart01.sh /service/runscripts/restart/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./test01.sh /service/runscripts/test/
ADD ./test02.sh /service/runscripts/test/
RUN chmod a+x /service/sbin/startnode;chmod a+x /service/runscripts/start/*;chmod a+x /service/runscripts/stop/*;chmod a+x /service/runscripts/test/*;chmod a+x /service/runscripts/restart/*

# Get rid of the apt-cache 
RUN rm -rf /var/cache/apt/archives/*
RUN rm -rf /var/lib/apt/lists/*
RUN rm /service/packages/*.tar.gz