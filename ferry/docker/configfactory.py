# Copyright 2014 OpenCore LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import logging
from pymongo import MongoClient
from ferry.install import FERRY_HOME, DEFAULT_TEMPLATE_DIR
from ferry.docker.docker import DockerInstance
from ferry.config.gluster.glusterconfig     import *
from ferry.config.hadoop.hadoopconfig       import *
from ferry.config.hadoop.hadoopclientconfig import *
from ferry.config.hadoop.metastore          import *
from ferry.config.spark.sparkconfig         import *
from ferry.config.spark.sparkclientconfig   import *
from ferry.config.openmpi.mpiconfig         import *
from ferry.config.openmpi.mpiclientconfig   import *
from ferry.config.titan.titanconfig         import *
from ferry.config.cassandra.cassandraconfig import *
from ferry.config.cassandra.cassandraclientconfig import *
from ferry.config.mongo.mongoconfig         import *
from ferry.config.mongo.mongoclientconfig   import *

class ConfigFactory(object):
    def __init__(self):
        self.gluster = GlusterInitializer()
        self.hadoop = HadoopInitializer()
        self.yarn = HadoopInitializer()
        self.hive = MetaStoreInitializer()
        self.spark = SparkInitializer()
        self.cassandra = CassandraInitializer()
        self.titan = TitanInitializer()
        self.mpi = OpenMPIInitializer()
        self.mongo = MongoInitializer()
        self.mongo_client = MongoClientInitializer()
        self.cassandra_client = CassandraClientInitializer()
        self.mpi_client = OpenMPIClientInitializer()
        self.hadoop_client = HadoopClientInitializer()
        self.spark_client = SparkClientInitializer()

        # Get the Ferry home to find the templates.
        template_dir = DEFAULT_TEMPLATE_DIR
        self.hadoop.template_dir =        template_dir + '/hadoop/'
        self.yarn.template_dir =          template_dir + '/hadoop/'
        self.spark.template_dir =         template_dir + '/spark/'
        self.spark_client.template_dir =  template_dir + '/spark/'
        self.hadoop_client.template_dir = template_dir + '/hadoop/'
        self.hive.template_dir =          template_dir + '/hive-metastore/'
        self.gluster.template_dir =       template_dir + '/gluster/'
        self.cassandra.template_dir =     template_dir + '/cassandra/'
        self.titan.template_dir =         template_dir + '/titan/'
        self.cassandra_client.template_dir =   template_dir + '/cassandra/'
        self.mpi.template_dir =           template_dir + '/openmpi/'
        self.mpi_client.template_dir =    template_dir + '/openmpi/'
        self.mongo.template_dir =         template_dir + '/mongo/'
        self.mongo_client.template_dir =  template_dir + '/mongo/'

    def _generate_configuration(self, uuid, container_info, config_factory):
        """
        Helper method to generate and copy over the configuration. 
        """
        config = config_factory.generate(len(container_info))
        config.uuid = uuid
        return config_factory.apply(config, container_info)

    def generate_compute_configuration(self, 
                                       uuid,
                                       containers,
                                       service,
                                       args, 
                                       storage_info):
        """
        Generate a compute-specific configuration. This configuration
        lives in its own directory that gets copied in each container. 
        """
        container_info = []
        for c in containers:
            s = {'data_dev':'eth0', 
                 'data_ip':c.internal_ip, 
                 'manage_ip':c.internal_ip,
                 'host_name':c.host_name,
                 'type':c.service_type}
            s['container'] = c
            s['storage'] = storage_info
            s['args'] = args

            container_info.append(s)

        return self._generate_configuration(uuid, 
                                            container_info, 
                                            service)

    def generate_storage_configuration(self, 
                                       uuid,
                                       containers,
                                       service, 
                                       args=None):
        """
        Generagte a storage-specific configuration. This configuration
        lives in its own directory that gets copied in each container. 
        """
        container_info = []
        for c in containers:
            s = {'data_dev':'eth0', 
                 'data_ip':c.internal_ip, 
                 'manage_ip':c.internal_ip,
                 'host_name':c.host_name,
                 'type':c.service_type}
            s['container'] = c
            s['args'] = args

            # Specify the data volume. There should only be one. 
            for v in c.volumes.keys():
                s['ebs_block'] = c.volumes[v]

            container_info.append(s)
        return self._generate_configuration(uuid, container_info, service) 

    def generate_connector_configuration(self, 
                                         uuid,
                                         containers,
                                         service, 
                                         storage_info=None,
                                         compute_info=None,
                                         args=None):
        """
        Generate a connector specific configuration. 
        """
        container_info = []
        for c in containers:
            s = {'data_dev':'eth0', 
                 'data_ip':c.internal_ip, 
                 'manage_ip':c.internal_ip,
                 'host_name':c.host_name}
            s['container'] = c
            s['args'] = args

            # Specify the entry point
            s['storage'] = storage_info
            s['compute'] = compute_info
            container_info.append(s)
        return self._generate_configuration(uuid, container_info, service) 

    def _generate_key_value(self,
                            json_data,
                            base_key):
        """
        Helper method to generate some environment variables. 
        """
        env = {}
        if type(json_data) is list:
            for j in json_data:
                values = self._generate_key_value(j, base_key)
                env = dict(env.items() + values.items())
        else:
            for k in json_data.keys():
                if type(json_data[k]) is unicode:
                    key = "%s_%s" % (base_key, k.upper())
                    value = json_data[k]
                    env[key] = value
                elif type(json_data[k]) is dict:
                    values = self._generate_key_value(json_data[k],
                                                      base_key + "_LAYER")
                    env = dict(env.items() + values.items())
        return env

    def generate_env_vars(self,
                          storage_info=None,
                          compute_info=None):
        """
        Generate some environment variables for the connectors. 
        These variables help the connectors query the backend. 
        """
        storage_values = {}
        compute_values = {}
        if storage_info:
            for s in storage_info:
                values = self._generate_key_value(s, "BACKEND_STORAGE")
                storage_values = dict(storage_values.items() + values.items())
                                                          
        if compute_info:
            for c in compute_info:
                values = self._generate_key_value(c, "BACKEND_COMPUTE")
                compute_values = dict(compute_values.items() + values.items())
                                                          
        return dict(storage_values.items() + compute_values.items())
