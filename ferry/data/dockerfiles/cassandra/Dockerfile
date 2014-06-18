FROM $USER/ferry-base
NAME cassandra

# Download the various packages needed
RUN apt-get --yes install openjdk-7-jdk

# Create necessary directories
RUN mkdir -p /service/data/main /service/logs /service/conf /service/data/cache /service/data/commits /service/sbin /service/package;chown -R ferry:docker /service/data;chown -R ferry:docker /service/logs;chown -R ferry:docker /service/conf

# Download the latest package
RUN wget $DOWNLOAD_URL/apache-cassandra-2.0.6-bin.tar.gz -P /service/package/
RUN cd /service/package;tar -xzf apache-cassandra-2.0.6-bin.tar.gz

# Get rid of the tarballs
RUN rm /service/package/*tar.gz

# Make soft links to the bin and configuration for easy access
RUN ln -s /service/package/apache-cassandra-2.0.6/bin /service;ln -s /service/package/apache-cassandra-2.0.6/conf /service/conf/cassandra
RUN ln -s /service/package/apache-cassandra-2.0.6/bin/* /usr/local/bin/

# Environment variables.
ENV CASSANDRA_HOME /service/package/apache-cassandra-2.0.6
ENV CASSANDRA_CONF /service/conf/cassandra
ENV CASSANDRA_INCLUDE /service/bin/cassandra.in.sh
RUN echo export JAVA_HOME=/usr/lib/jvm/java-7-openjdk-amd64 >> /etc/profile
RUN echo export CASSANDRA_HOME=/service/package/apache-cassandra-2.0.6 >> /etc/profile
RUN echo export CASSANDRA_CONF=/service/conf/cassandra >> /etc/profile
RUN echo export CASSANDRA_INCLUDE=/service/bin/cassandra.in.sh >> /etc/profile

# Add the control script to the image. 
ADD ./startnode /service/sbin/
RUN chmod a+x /service/sbin/startnode
