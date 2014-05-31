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

import sh
import sys
from string import Template

class TitanInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = TitanConfig.data_directory 
        self.container_log_dir = TitanConfig.log_directory 

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'titan' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        output = fabric.cmd(containers, '/service/sbin/startnode %s' % cmd)
    def start_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "start")
    def stop_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "stop")

    def _generate_config_dir(self, uuid, container):
        return 'titan_' + str(uuid) + '_' + str(container['data_ip'])

    """
    Get the ports necessary. 
    """
    def get_necessary_ports(self, num_instances):
        return []
    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return [TitanConfig.REXSTER_PORT, 
                TitanConfig.REXPRO_PORT, 
                TitanConfig.THRIFT_COM_PORT,
                TitanConfig.NATIVE_COM_PORT]

    """
    Generate a new configuration
    """
    def generate(self, num):
        return TitanConfig(num)

    def _apply_rexster(self, host_dir, storage_entry, container):
        in_file = open(self.template_dir + '/rexster.xml.template', 'r')
        out_file = open(host_dir + '/rexster.xml', 'w+')
        changes = { "GRAPH_BACKEND":storage_entry['type'], 
                    "GRAPH_HOST":storage_entry['seed'],
                    "GRAPH_NAME":container['args']['db'],
                    "IP":container['data_ip']}
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)
        out_file.close()
        in_file.close()

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

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers, storage_entry=None):
        # The "entry point" is the way to contact the storage service.
        entry_point = { 'type' : 'titan' }
    
        # List all the containers in the entry point so that
        # clients can connect any of them. 
        entry_point['ip'] = str(containers[0]['data_ip'])

        config_dirs = []
        try:
            for c in containers:
                host_dir = "/tmp/" + self._generate_config_dir(config.uuid, c)
                try:
                    sh.mkdir('-p', host_dir)
                except:
                    sys.stderr.write('could not create config dir ' + host_dir)

                self._apply_rexster(host_dir, storage_entry, c)
                self._apply_titan(host_dir, storage_entry, c)

                # The config dirs specifies what to transfer over. We want to 
                # transfer over specific files into a directory. 
                config_dirs.append([c['container'], 
                                    host_dir + '/*', 
                                    config.config_directory])

        except IOError as err:
            sys.stderr.write('' + str(err))

        return config_dirs, entry_point

class TitanConfig(object):
    data_directory = '/service/data/main/'
    log_directory = '/service/data/logs/'
    config_directory = '/service/conf/titan/'

    REXSTER_PORT = 8182
    REXPRO_PORT = 8184
    THRIFT_COM_PORT  = 9160
    NATIVE_COM_PORT  = 9042

    def __init__(self, num):
        self.num = num
        self.config_directory = TitanConfig.config_directory
