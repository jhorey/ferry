FROM $USER/gluster
NAME hadoop-base

# Make the various directories needed
RUN mkdir -p /service/packages /service/data/main /service/data/hive /service/data/logs /service/data/tmp /service/data/staging /service/sbin /service/scripts

# Download some dependencies
RUN apt-get --yes install openjdk-7-jdk zlib1g lib32z1 libpostgresql-jdbc-java software-properties-common
RUN wget https://www.dropbox.com/s/bjwo9bania20cfm/hadoop-2.3.0.tar.gz -P /service/packages;cd /service/packages;tar -xzf hadoop-2.3.0.tar.gz
RUN wget https://www.dropbox.com/s/nzp0a5zucvto1sf/hive-0.12.0.tar.gz -P /service/packages;cd /service/packages;tar -xzf hive-0.12.0.tar.gz

# untar tarball and  move the untarred files to /hadoop
RUN ln -s /service/packages/hadoop-2.3.0/etc/hadoop /service/conf;ln -s /service/packages/hadoop-2.3.0 /service/packages/hadoop;ln -s /service/packages/hive-0.12.0 /service/packages/hive;ln -s /usr/share/java/postgresql-jdbc4.jar /service/packages/hive/lib/postgresql-jdbc4.jar

# Make ferry owner of everything. 
RUN chown -R ferry:docker /service

RUN echo export JAVA_HOME=/usr/lib/jvm/java-7-openjdk-amd64 >> /etc/profile;echo export HADOOP_HOME=/service/packages/hadoop >> /etc/profile;echo export HIVE_HOME=/service/packages/hive >> /etc/profile;echo export JAVA_LIBRARY_PATH=/service/packages/hadoop/lib/native/ >> /etc/profile
ENV JAVA_HOME /usr/lib/jvm/java-7-openjdk-amd64
ENV HADOOP_HOME /service/packages/hadoop
ENV HIVE_HOME /service/packages/hive
ENV JAVA_LIBRARY_PATH /service/packages/hadoop/lib/native/