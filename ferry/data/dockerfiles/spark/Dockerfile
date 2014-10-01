FROM $USER/hadoop-base
NAME spark
NAME spark-client

# Make the various directories needed
RUN mkdir -p /service/runscripts/start /service/runscripts/restart /service/runscripts/test /service/runscripts/stop

# Install everything. Spark needs a newer version of Numpy, so we'll need to
# use `pip` to install it. 
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get --yes install build-essential git scala libgfortran3 jblas python-pip python-dev
RUN pip install numpy

# Add the binaries
RUN wget $DOWNLOAD_URL/spark-1.1.0-bin-hadoop2.4.tgz -P /service/packages/ 
# RUN wget $DOWNLOAD_URL/spark-assembly_2.10-0.9.1-hadoop2.3.0.jar -P /service/packages/
RUN cd /service/packages; tar -xzf spark-1.1.0-bin-hadoop2.4.tgz

# Make some symlinks
RUN ln -s /service/packages/spark-1.1.0-bin-hadoop2.4 /service/packages/spark
RUN ln -s /service/packages/spark/conf /service/conf/spark

# Add all the scripts. 
ADD ./startnode /service/sbin/
ADD ./start01.sh /service/runscripts/start/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./restart01.sh /service/runscripts/restart/
ADD ./test01.sh /service/runscripts/test/
RUN chmod a+x /service/sbin/startnode;chmod a+x /service/runscripts/start/*;chmod a+x /service/runscripts/stop/*;chmod a+x /service/runscripts/restart/*;chmod a+x /service/runscripts/test/*

# Example scripts
RUN mkdir -p /service/examples/python
RUN mkdir -p /service/examples/data
ADD ./classification.py /service/examples/python/
ADD ./clustering.py /service/examples/python/
ADD ./filtering.py /service/examples/python/
ADD ./regression.py /service/examples/python/
ADD ./kmeans_test.data /service/examples/data/
ADD ./lpsa_test.data /service/examples/data/
ADD ./svm_test.data /service/examples/data/
ADD ./als_test.data /service/examples/data/
ADD ./tree_test.data /service/examples/data/

# Environment variables
ENV SPARK_HOME /service/packages/spark
RUN echo export SPARK_HOME=/service/packages/spark >> /etc/profile
# ENV SPARK_JAR /service/packages/spark-assembly_2.10-0.9.1-hadoop2.3.0.jar
ENV SPARK_JAR /service/packages/spark/lib/spark-assembly-1.1.0-hadoop2.4.0.jar
# RUN echo export SPARK_JAR=/service/packages/spark-assembly_2.10-0.9.1-hadoop2.3.0.jar >> /etc/profile
RUN echo export SPARK_JAR=/service/packages/spark/lib/spark-assembly-1.1.0-hadoop2.4.0.jar >> /etc/profile
RUN echo export PATH=$$PATH:$$SPARK_HOME/sbin:$$SPARK_HOME/bin >> /etc/profile
ENV SPARK_YARN_APP_JAR /service/packages/spark/examples/target/spark-examples_2.10-0.9.1-sources.jar
RUN echo export SPARK_YARN_APP_JAR=/service/packages/spark/examples/target/spark-examples_2.10-0.9.1-sources.jar >> /etc/profile

# Generate an ssh key for this image.
RUN mkdir /home/ferry/.ssh;ssh-keygen -f /home/ferry/.ssh/id_rsa -t rsa -N '' > /dev/null
RUN cat /home/ferry/.ssh/id_rsa.pub >> /home/ferry/.ssh/authorized_keys;echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config;touch /etc/mtab
RUN chown -R ferry:ferry /home/ferry/.ssh

# Remove any intermediate packages
RUN rm /service/packages/*.tgz
RUN rm -rf /var/cache/apt/archives/*
RUN rm -rf /var/lib/apt/lists/*