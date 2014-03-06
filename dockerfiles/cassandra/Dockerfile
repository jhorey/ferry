FROM $USER/drydock-base
NAME cassandra

# Download the various packages needed
RUN apt-get --yes install openjdk-7-jdk

# Create necessary directories
RUN mkdir -p /service/data/main /service/logs /service/data/cache /service/data/commits /service/sbin /service/package;chown -R drydock:docker /service/data;chown -R drydock:docker /service/logs

# Download the latest package
RUN wget http://mirrors.ibiblio.org/apache/cassandra/2.0.5/apache-cassandra-2.0.5-bin.tar.gz -P /service/package/;cd /service/package;tar -xzf apache-cassandra-2.0.5-bin.tar.gz

# Make soft links to the bin and configuration for easy access
RUN ln -s /service/package/apache-cassandra-2.0.5/bin /service;ln -s /service/package/apache-cassandra-2.0.5/conf /service

# Environment variables.
RUN echo export JAVA_HOME=/usr/lib/jvm/java-7-openjdk-amd64 >> /etc/profile
RUN echo export CASSANDRA_HOME=/service/package/apache-cassandra-2.0.5 >> /etc/profile
RUN echo export CASSANDRA_CONF=/service/conf >> /etc/profile
RUN echo export CASSANDRA_INCLUDE=/service/bin/cassandra.in.sh >> /etc/profile

# Add the control script to the image. 
ADD ./startnode /service/sbin/

# Run the ssh daemon in the foreground (Docker does
# like daemons running in background)
CMD ["/service/sbin/startnode", "listen"]
