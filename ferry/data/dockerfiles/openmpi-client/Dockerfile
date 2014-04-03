FROM $USER/openmpi
NAME openmpi-client

# Add the control script to the image. 
ADD ./helloworld.cpp /service/examples/
ADD ./test01.sh /service/runscripts/test/
RUN chmod a+x /service/runscripts/test/
