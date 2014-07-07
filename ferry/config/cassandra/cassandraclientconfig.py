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

import sys
import sh
from string import Template
from ferry.docker.fabric import DockerFabric

class CassandraClientInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = CassandraClientConfig.data_directory
        self.container_log_dir = CassandraClientConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'cassandra_client' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        return fabric.cmd(containers, 
                          '/service/sbin/startnode %s %s' % (cmd, entry_point['cassandra_url']))
    def start_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "stop")

    def _generate_config_dir(self, uuid):
        return 'cassandra_client' + str(uuid)

    """
    Get the ports necessary for Gluster. 
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return []

    """
    Get total number of instances.
    """
    def get_total_instances(self, num_instances, layers):
        instances = []

        for i in range(num_instances):
            instances.append('cassandra-client')

        return instances

    """
    Generate a new configuration
    """
    def generate(self, num):
        return CassandraClientConfig(num)

    def _apply_cassandra(self, host_dir, entry_point, config, container):
        yaml_in_file = open(self.template_dir + '/cassandra.yaml.template', 'r')
        yaml_out_file = open(host_dir + '/cassandra.yaml', 'w+')

        # Now make the changes to the template file. 
        changes = { "LOCAL_ADDRESS":container['data_ip'], 
                    "DATA_DIR":config.data_directory,
                    "CACHE_DIR":config.cache_directory,
                    "COMMIT_DIR":config.commit_directory,
                    "SEEDS":entry_point['cassandra_url']}

        for line in yaml_in_file:
            s = Template(line).substitute(changes)
            yaml_out_file.write(s)

        yaml_out_file.close()
        yaml_in_file.close()

    def _apply_titan(self, host_dir, storage_entry, container):
        in_file = open(self.template_dir + '/titan.properties', 'r')
        out_file = open(host_dir + '/titan.properties', 'w+')
        changes = { "BACKEND":"cassandrathrift", 
                    "DB":container['args']['db'],
                    "IP":storage_entry['seed']}
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)
        out_file.close()
        in_file.close()

    def _find_cassandra_storage(self, containers):
        """
        Find a Cassandra compatible storage entry. 
        """
        for c in containers:
            for s in c['storage']:
                if s['type'] == 'cassandra':
                    return s

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        entry_point = { 'type' : 'cassandra-client' }
        entry_point['ip'] = containers[0]['data_ip']

        # Get the storage information. 
        storage_entry = self._find_cassandra_storage(containers)
        if not storage_entry:
            # The Cassandra client is currently only compatible with a 
            # Cassandra backend. So just return an error.
            return None, None

        # Otherwise record the storage type and get the seed node. 
        entry_point['cassandra_url'] = storage_entry['seed']

        # Create a new configuration directory, and place
        # into the template directory. 
        config_dirs = []

        try:
            host_dir = "/tmp/" + self._generate_config_dir(config.uuid)
            try:
                sh.mkdir('-p', host_dir)
            except:
                sys.stderr.write('could not create config dir ' + host_dir)

            self._apply_cassandra(host_dir, entry_point, config, containers[0])

            # See if we need to apply
            if 'titan' in storage_entry:
                self._apply_titan(host_dir, storage_entry, containers[0])
                out_file = open(host_dir + '/servers', 'w+')
                out_file.write("%s %s" % (storage_entry['titan']['ip'], 'rexserver'))
                out_file.close

            # The config dirs specifies what to transfer over. We want to 
            # transfer over specific files into a directory. 
            for c in containers:
                config_dirs.append([c['container'], 
                                    host_dir + '/*', 
                                    config.config_directory])
        except IOError as err:
            sys.stderr.write('' + str(err))

        return config_dirs, entry_point

class CassandraClientConfig(object):
    data_directory = '/service/data/main/'
    log_directory = '/service/data/logs/'
    commit_directory = '/service/data/commits/'
    cache_directory = '/service/data/cache/'
    config_directory = '/service/conf/cassandra/'

    def __init__(self, num):
        self.num = num
        self.data_directory = CassandraClientConfig.data_directory
        self.commit_directory = CassandraClientConfig.commit_directory
        self.cache_directory = CassandraClientConfig.cache_directory
        self.log_directory = CassandraClientConfig.log_directory
        self.config_directory = CassandraClientConfig.config_directory
