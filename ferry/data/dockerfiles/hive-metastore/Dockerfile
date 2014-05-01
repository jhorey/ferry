FROM $USER/hadoop-base
NAME hive-metastore
NAME hive

# Add the control script to the image. 
ADD ./startnode /service/sbin/
ADD ./createstore.sql /service/sbin/
ADD ./hive-schema.sql /service/sbin/
RUN chmod a+x /service/sbin/startnode

# Download some dependencies
RUN apt-get --yes install language-pack-en-base postgresql
