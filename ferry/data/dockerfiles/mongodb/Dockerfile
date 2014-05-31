FROM $USER/ferry-base
NAME mongodb
NAME mongodb-client

# Add the 10Gen key and repo
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv 7F0CEB10;echo "deb http://downloads-distro.mongodb.org/repo/ubuntu-upstart dist 10gen" >> /etc/apt/sources.list

# Update the repository for latest packages
RUN apt-get update;apt-get --yes install mongodb-org python-pip python-dev build-essential

# To download pymongo
RUN pip install --upgrade virtualenv;pip install pymongo

# Create default data directory
RUN mkdir -p /service/com /service/sbin /service/data /service/logs /service/conf/mongodb
RUN chown -R ferry:docker /service

# Export data directory path
ENV MONGO_DATA /service/data
ENV MONGO_LOG /service/logs/mongodb.log
RUN echo export MONGO_DATA=/service/data >> /etc/profile;echo export MONGO_LOG=/service/logs/mongodb.log >> /etc/profile

# Used to address Mongo bug
ENV LC_ALL C
RUN echo export LC_ALL=C >> /etc/profile

# Add the start script
ADD ./createadmin.js /service/sbin/
ADD ./startnode /service/sbin/
RUN chmod a+x /service/sbin/startnode
