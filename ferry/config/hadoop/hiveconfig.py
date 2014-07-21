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
import sh
import sys
from string import Template
from ferry.docker.fabric import DockerFabric

class HiveClientInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = HiveClientConfig.data_directory
        self.container_log_dir = HiveClientConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'hive-client' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        output = fabric.cmd(containers, '/service/sbin/startnode %s client' % cmd)

    """
    Generate a new configuration.
    """
    def _generate_config_dir(self, uuid):
        return 'hive_client_' + str(uuid)

    """
    Get the ports necessary. 
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return []

    """
    Generate a new configuration
    """
    def generate(self, num):
        return HiveClientConfig(num)

    """
    Generate the hive site configuration. 
    """
    def _generate_hive_site(self, config, new_config_dir):
        in_file = open(self.template_dir + '/hive-site.xml.template', 'r')
        out_file = open(new_config_dir + '/hive-site.xml', 'w+')
        
        changes = { "DB":config.metastore,
                    "USER": os.environ['USER'] }
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        # The "entry point" is the way to contact the storage service.
        # For gluster this is the IP address of the "master" and the volume name. 
        entry_point = { 'type' : 'hive' }

        # Create a new configuration directory, and place
        # into the template directory. 
        config_dirs = []
        new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid)
        try:
            sh.mkdir('-p', new_config_dir)
        except:
            sys.stderr.write('could not create config dir ' + new_config_dir)

        self._generate_hive_site(config, new_config_dir)

        # Each container needs to point to a new config dir. 
        for c in containers:
            config_files = new_config_dir + '/*'
            config_dirs.append([c['container'],
                                config_files, 
                                config.config_directory])

        return config_dirs, entry_point

class HiveClientConfig(object):
    data_directory = '/service/data/main'
    log_directory = '/service/data/logs'
    config_directory = '/service/conf/hive'
    def __init__(self, num):
        self.num = num
        self.config_directory = HiveClientConfig.config_directory
        self.hadoop_config_dir = None
        self.metastore = None
