FROM $USER/hadoop-base
NAME hadoop
NAME yarn

## Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./mounthelper.py /service/scripts/
RUN chmod a+x /service/sbin/startnode

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "init"]