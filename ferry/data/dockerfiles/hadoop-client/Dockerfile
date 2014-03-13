FROM $USER/hadoop-base
NAME hadoop-client

# Make the various directories needed
RUN mkdir -p /service/runscripts/start /service/runscripts/restart /service/runscripts/test /service/runscripts/stop

# Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./createtable.sql /service/scripts/
ADD ./mounthelper.py /service/scripts/
ADD ./start01.sh /service/runscripts/start/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./test01.sh /service/runscripts/test/
ADD ./test02.sh /service/runscripts/test/
RUN chmod a+x /service/sbin/startnode;chmod a+x /service/runscripts/start/*;chmod a+x /service/runscripts/stop/*;chmod a+x /service/runscripts/test/*

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "listen"]