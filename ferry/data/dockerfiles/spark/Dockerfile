FROM ferry/hadoop-client
NAME ferry/spark

# Install everything
RUN apt-get --yes install git scala emacs

# Add the binaries
ADD ./spark-0.9.1-bin-hadoop2.tgz /service/packages/
ADD ./spark-assembly_2.10-0.9.1-hadoop2.3.0.jar /service/packages/

RUN ln -s /service/packages/spark-0.9.1-bin-hadoop2 /service/packages/spark

ADD ./startnode /service/sbin/
ADD ./start01.sh /service/runscripts/start/
ADD ./stop10.sh /service/runscripts/stop/
ADD ./restart01.sh /service/runscripts/restart/
ADD ./test01.sh /service/runscripts/test/
RUN chmod a+x /service/sbin/startnode;chmod a+x /service/runscripts/start/*;chmod a+x /service/runscripts/stop/*;chmod a+x /service/runscripts/restart/*;chmod a+x /service/runscripts/test/*

# Environment variables
ENV SPARK_HOME /service/packages/spark
RUN echo export SPARK_HOME=/service/packages/spark >> /etc/profile
ENV SPARK_JAR /service/packages/spark-assembly_2.10-0.9.1-hadoop2.3.0.jar
RUN echo export SPARK_JAR=/service/packages/spark-assembly_2.10-0.9.1-hadoop2.3.0.jar >> /etc/profile
RUN echo export PATH=$PATH:$SPARK_HOME/sbin:$SPARK_HOME/bin >> /etc/profile

# This is something that the Hadoop base package should do. 
ENV HADOOP_CONF_DIR /service/conf
RUN echo export HADOOP_CONF_DIR=/service/conf >> /etc/profile

# Generate an ssh key for this image.
RUN mkdir /home/ferry/.ssh;ssh-keygen -f /home/ferry/.ssh/id_rsa -t rsa -N '' > /dev/null
RUN cat /home/ferry/.ssh/id_rsa.pub >> /home/ferry/.ssh/authorized_keys;echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config;touch /etc/mtab
RUN chown -R ferry:ferry /home/ferry/.ssh

CMD ["/service/sbin/startnode", "init"]

# This will need to be replaced with the actual appliation JAR file
RUN touch /tmp/fake.txt
ENV SPARK_YARN_APP_JAR /tmp/fake.txt
RUN echo export SPARK_YARN_APP_JAR=/tmp/fake.txt >> /etc/profile
