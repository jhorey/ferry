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

import logging
import os
import sh
import sys
import time
from string import Template

class SparkInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = None
        self.container_log_dir = SparkConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'spark' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        all_output = {}
        master = entry_point['master']
        for c in containers:
            if c.host_name == master:
                output = fabric.cmd([c], '/service/sbin/startnode %s master' % cmd)
            else:
                output = fabric.cmd([c], '/service/sbin/startnode %s slave' % cmd)
            all_output = dict(all_output.items() + output.items())

        # Now wait a couple seconds to make sure
        # everything has started.
        time.sleep(4)
        return all_output
    def start_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        return self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):        
        return self._execute_service(containers, entry_point, fabric, "stop")
    """
    Generate a new configuration.
    """
    def _generate_config_dir(self, uuid):
        return 'spark_' + str(uuid)

    """
    Get the ports necessary.
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        return [SparkConfig.MASTER_PORT,
                SparkConfig.SLAVE_PORT,
                SparkConfig.WEBUI_MASTER,
                SparkConfig.WEBUI_SLAVE]

    def get_total_instances(self, num_instances, layers):
        instances = []

        for i in range(num_instances):
            instances.append('spark')

        return instances

    """
    Generate a new configuration
    Param num Number of instances that need to be configured
    Param image Image type of the instances
    """
    def generate(self, num):
        return SparkConfig(num)

    """
    Generate the core-site configuration for a local filesystem. 
    """
    def _generate_spark_env(self, new_config_dir, master):
        in_file = open(self.template_dir + '/spark_env.sh.template', 'r')
        out_file = open(new_config_dir + '/spark_env.sh', 'w+')

        changes = { "MASTER": master }
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

        # The Spark env file is a shell script, so should be
        # executable by all. 
        os.chmod(new_config_dir + '/spark_env.sh', 0755)

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        entry_point = { 'type' : 'spark' }
        config_dirs = []

        new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid)
        try:
            sh.mkdir('-p', new_config_dir)
        except:
            sys.stderr.write('could not create config dir ' + new_config_dir)

        # This file records all instances so that we can
        # generate the hosts file. 
        entry_point['instances'] = []
        for server in containers:
            entry_point['instances'].append([server['data_ip'], server['host_name']])

        if not 'compute' in containers[0]:
            # This is being called as a compute service. 
            slave_file = open(new_config_dir + '/slaves', 'w+')
            entry_point['master'] = containers[0]['host_name']
            entry_point['instances'] = []
            master = entry_point['master']
            for server in containers:
                if server != master:
                    slave_file.write("%s\n" % server['host_name'])
            slave_file.close()
        else:
            # This is being called as a client service. 
            # For the client, also include the host/IP of the compute service. 
            compute = containers[0]['compute'][0]
            entry_point['master'] = compute['master']

        # Transfer the configuration. 
        for c in containers:
            config_files = new_config_dir + '/*'
            config_dirs.append([c['container'],
                                config_files, 
                                config.config_directory])

        return config_dirs, entry_point

class SparkConfig(object):
    log_directory = '/service/packages/spark/logs/'
    config_directory = '/service/conf/spark/'

    MASTER_PORT = 7077
    SLAVE_PORT = 7078
    WEBUI_MASTER = 8080
    WEBUI_SLAVE = 8081

    def __init__(self, num):
        self.num = num
        self.btl_port_min = 0
        self.btl_port_range = 0
        self.oob_port_min = 0
        self.oob_port_range = 0
        self.config_directory = SparkConfig.config_directory
        self.log_directory = SparkConfig.log_directory
