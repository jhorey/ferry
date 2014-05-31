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
import sys
import sh
from string import Template
from ferry.install import FERRY_HOME
from ferry.docker.fabric import DockerFabric
from ferry.config.titan.titanconfig import *

class CassandraInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.titan = TitanInitializer()
        self.titan.template_dir = FERRY_HOME + '/data/templates/titan'

        self.container_data_dir = CassandraConfig.data_directory
        self.container_log_dir = CassandraConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'cassandra' + str(instance_id)

    def _execute_service(self, containers, entry_point, fabric, cmd):
        for c in containers:
            if c.service_type == 'cassandra':
                output = fabric.cmd([c], '/service/sbin/startnode %s' % cmd)
            elif c.service_type == 'titan':
                self.titan._execute_service([c], entry_point, fabric, cmd)

    def start_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "stop")

    def _generate_config_dir(self, uuid, container):
        return 'cassandra_' + str(uuid) + '_' + str(container['data_ip'])

    """
    Get the ports necessary. 
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        ports = []
        
        ports.append(CassandraConfig.CLUSTER_COM_PORT)
        ports.append(CassandraConfig.CLUSTER_SSL_PORT)
        ports.append(CassandraConfig.THRIFT_COM_PORT)
        ports.append(CassandraConfig.NATIVE_COM_PORT)
        ports.append(CassandraConfig.JMX_PORT)
        ports.append(CassandraConfig.RMI_PORT)

        return ports

    """
    Get total number of instances.
    """
    def get_total_instances(self, num_instances, layers):
        instances = []

        for i in range(num_instances):
            instances.append('cassandra')

        if len(layers) > 0 and layers[0] == "titan":
            instances.append('titan')

        return instances

    """
    Generate a new configuration
    """
    def generate(self, num):
        return CassandraConfig(num)

    """
    Generate Titan configuration. 
    """
    def _apply_titan(self, config, cass_entry, cass_containers):
        return self.titan.apply(config, cass_containers, cass_entry)

    def _generate_yaml_config(self, container, seed, host_dir, config):
        yaml_in_file = open(self.template_dir + '/cassandra.yaml.template', 'r')
        yaml_out_file = open(host_dir + '/cassandra.yaml', 'w+')

        changes = { "LOCAL_ADDRESS":container['data_ip'], 
                    "DATA_DIR":config.data_directory,
                    "CACHE_DIR":config.cache_directory,
                    "COMMIT_DIR":config.commit_directory,
                    "SEEDS":seed}

        for line in yaml_in_file:
            s = Template(line).substitute(changes)
            yaml_out_file.write(s)

        yaml_out_file.close()
        yaml_in_file.close()

    def _generate_log4j_config(self, host_dir, config):
        log4j_in_file = open(self.template_dir + '/log4j-server.properties', 'r')
        log4j_out_file = open(host_dir + '/log4j-server.properties', 'w+')

        changes = { "LOG_DIR":config.log_directory } 

        for line in log4j_in_file:
            s = Template(line).substitute(changes)
            log4j_out_file.write(s)

        log4j_out_file.close()
        log4j_in_file.close()

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        # The "entry point" is the way to contact the storage service.
        entry_point = { 'type' : 'cassandra' }

        cass_containers = []
        titan_containers = []
        for c in containers:
            if c['type'] == 'cassandra':
                cass_containers.append(c)
            elif c['type'] == 'titan':
                titan_containers.append(c)

        # In Cassandra all nodes are equal, so just pick one
        # as the "entry" node
        entry_point['seed'] = str(containers[0]['data_ip'])

        # Generate list of the seed nodes. We don't need the entire
        # list of containers, just a few. 
        seed = ''
        for i in range(0, len(cass_containers)):
            if i < 6:
                if i != 0:
                    seed += ','
                seed += cass_containers[i]['data_ip']

        # Create a new configuration directory, and place
        # into the template directory. 
        config_dirs = []
        try:
            for c in cass_containers:
                host_dir = "/tmp/" + self._generate_config_dir(config.uuid, c)
                try:
                    sh.mkdir('-p', host_dir)
                except:
                    sys.stderr.write('could not create config dir ' + host_dir)

                # The config dirs specifies what to transfer over. We want to 
                # transfer over specific files into a directory. 
                config_dirs.append([c['container'], 
                                    host_dir + '/*', 
                                    config.config_directory])

                self._generate_yaml_config(c, seed, host_dir, config)
                self._generate_log4j_config(host_dir, config)
        except IOError as err:
            sys.stderr.write('' + str(err))

        if len(titan_containers) > 0:
            # We need to configure a Titan container. 
            titan_config = self.titan.generate(len(titan_containers))
            titan_config.uuid = config.uuid
            titan_dirs, titan_entry = self._apply_titan(titan_config, entry_point, titan_containers)
            config_dirs.extend(titan_dirs)
            entry_point['titan'] = titan_entry

        return config_dirs, entry_point

class CassandraConfig(object):
    data_directory = '/service/data/main'
    log_directory = '/service/logs'
    commit_directory = '/service/data/commits'
    cache_directory = '/service/data/cache'
    config_directory = '/service/conf/cassandra'

    CLUSTER_COM_PORT = 7000
    CLUSTER_SSL_PORT = 7001
    THRIFT_COM_PORT  = 9160
    NATIVE_COM_PORT  = 9042
    JMX_PORT         = 7199
    RMI_PORT         = 7200

    def __init__(self, num):
        self.num = num
        self.data_directory = CassandraConfig.data_directory
        self.commit_directory = CassandraConfig.commit_directory
        self.cache_directory = CassandraConfig.cache_directory
        self.log_directory = CassandraConfig.log_directory
        self.config_directory = CassandraConfig.config_directory
