FROM $USER/gluster
NAME hadoop-base

# Make the various directories needed
RUN mkdir -p /service/packages /service/conf /service/data/main /service/data/hive /service/data/logs /service/data/tmp /service/data/staging /service/scripts

# Download some dependencies
RUN apt-get --yes install openjdk-7-jdk zlib1g lib32z1 libpostgresql-jdbc-java software-properties-common
RUN wget $DOWNLOAD_URL/hadoop-2.3.0.tar.gz -P /service/packages
RUN wget $DOWNLOAD_URL/hive-0.12.0.tar.gz -P /service/packages
RUN cd /service/packages;tar -xzf hadoop-2.3.0.tar.gz
RUN cd /service/packages;tar -xzf hive-0.12.0.tar.gz

# Get rid of the tarballs. 
RUN rm /service/packages/*.tar.gz

# Make symlinks
RUN ln -s /service/packages/hadoop-2.3.0/etc/hadoop /service/conf/hadoop;ln -s /service/packages/hive-0.12.0/conf /service/conf/hive;ln -s /service/packages/hadoop-2.3.0/logs /service/logs/hadoop;ln -s /service/packages/hadoop-2.3.0 /service/packages/hadoop;ln -s /service/packages/hive-0.12.0 /service/packages/hive;ln -s /usr/share/java/postgresql-jdbc4.jar /service/packages/hive/lib/postgresql-jdbc4.jar

# Soft links to make life easier
RUN ln -s /service/packages/hadoop/bin/* /usr/local/bin/
RUN ln -s /service/packages/hive/bin/* /usr/local/bin/

# Make ferry owner of everything. 
RUN chown -R ferry:docker /service

ENV JAVA_HOME /usr/lib/jvm/java-7-openjdk-amd64
ENV HADOOP_HOME /service/packages/hadoop
ENV HADOOP_CONF_DIR /service/conf/hadoop
ENV HIVE_HOME /service/packages/hive
ENV HADOOP_LIBEXEC_DIR /service/packages/hadoop/libexec
ENV JAVA_LIBRARY_PATH /service/packages/hadoop/lib/native/
RUN echo export JAVA_HOME=/usr/lib/jvm/java-7-openjdk-amd64 >> /etc/profile;echo export HADOOP_HOME=/service/packages/hadoop >> /etc/profile;echo export HIVE_HOME=/service/packages/hive >> /etc/profile;echo export HADOOP_LIBEXEC_DIR=/service/packages/hadoop/libexec >> /etc/profile;echo export JAVA_LIBRARY_PATH=/service/packages/hadoop/lib/native/ >> /etc/profile;echo export HADOOP_CONF_DIR=/service/conf/hadoop >> /etc/profile
