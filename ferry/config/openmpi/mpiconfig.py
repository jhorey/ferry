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
import sh
import sys
from string import Template

class OpenMPIInitializer(object):
    """
    Create a new initializer
    Param user The user login for the git repo
    """
    def __init__(self):
        self.template_dir = None
        self.template_repo = None

        self.container_data_dir = None
        self.container_log_dir = MPIConfig.log_directory

    """
    Generate a new hostname
    """
    def new_host_name(self, instance_id):
        return 'openmpi' + str(instance_id)

    """
    Start the service on the containers. 
    """
    def _execute_service(self, containers, entry_point, fabric, cmd):
        output = fabric.cmd(containers, '/service/sbin/startnode %s %s' % (cmd, entry_point['mount']))
    def start_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "start")
    def restart_service(self, containers, entry_point, fabric):
        self._execute_service(containers, entry_point, fabric, "restart")
    def stop_service(self, containers, entry_point, fabric):        
        self._execute_service(containers, entry_point, fabric, "stop")
    """
    Generate a new configuration.
    """
    def _generate_config_dir(self, uuid):
        return 'openmpi_' + str(uuid)

    """
    Get the ports necessary.
    """
    def get_necessary_ports(self, num_instances):
        return []

    """
    Get the internal ports. 
    """
    def get_exposed_ports(self, num_instances):
        BTL_PORT_END = MPIConfig.BTL_PORT_MIN + (MPIConfig.PORT_RANGE * num_instances)
        OOB_PORT_END = MPIConfig.OOB_PORT_MIN + (MPIConfig.PORT_RANGE * num_instances)
        BTL_PORTS = '%s-%s' % (MPIConfig.BTL_PORT_MIN, BTL_PORT_END)
        OOB_PORTS = '%s-%s' % (MPIConfig.OOB_PORT_MIN, OOB_PORT_END)
        return [BTL_PORTS, OOB_PORTS]

    def get_total_instances(self, num_instances, layers):
        instances = []

        for i in range(num_instances):
            instances.append('openmpi')

        return instances

    """
    Generate a new configuration
    Param num Number of instances that need to be configured
    Param image Image type of the instances
    """
    def generate(self, num):
        config = MPIConfig(num)
        config.btl_port_min = MPIConfig.BTL_PORT_MIN
        config.oob_port_min = MPIConfig.OOB_PORT_MIN
        config.btl_port_range = MPIConfig.PORT_RANGE * num
        config.oob_port_range = MPIConfig.PORT_RANGE * num

        return config

    """
    Generate the mca-params configuration. 
    """
    def _generate_mca_params(self, config, new_config_dir):
        in_file = open(self.template_dir + '/openmpi-mca-params.conf', 'r')
        out_file = open(new_config_dir + '/openmpi-mca-params.conf', 'w+')

        changes = { "BTL_PORT_MIN": config.btl_port_min,
                    "BTL_PORT_RANGE": config.btl_port_range,
                    "OOB_PORT_MIN": config.oob_port_min,
                    "OOB_PORT_RANGE": config.oob_port_range }
        for line in in_file:
            s = Template(line).substitute(changes)
            out_file.write(s)

        in_file.close()
        out_file.close()

    """
    Apply the configuration to the instances
    """
    def apply(self, config, containers):
        entry_point = { 'type' : 'openmpi' }
        config_dirs = []

        new_config_dir = "/tmp/" + self._generate_config_dir(config.uuid)
        try:
            sh.mkdir('-p', new_config_dir)
        except:
            sys.stderr.write('could not create config dir ' + new_config_dir)

        # For now the MPI client assumes there is only one storage and that it is
        # a Gluster end point. 
        storage = containers[0]['storage'][0]
        if storage['type'] == 'gluster':
            mount_ip = storage['ip']
            mount_dir = storage['volume']
            entry_point['mount'] = "%s:/%s" % (mount_ip, mount_dir)

            # Check if we are being called as a compute instance or client
            # instance. If compute, the we must generate the host file. 
            instances_file = open(new_config_dir + '/instances', 'w+')
            if not 'compute' in containers[0]:
                entry_point['instances'] = []
                for server in containers:
                    instances_file.write("%s %s\n" % (server['data_ip'], server['host_name']))
                    entry_point['instances'].append([server['data_ip'], server['host_name']])
            else:
                # This is the MPI client. The instance file only contains the IP
                # address of the compute nodes (instead of the IP + hostname) so that
                # MPI will remain happy. 
                entry_point['ip'] = containers[0]['data_ip']
                compute = containers[0]['compute'][0]
                for s in compute['instances']:
                    instances_file.write("%s\n" % s[0])
                instances_file.close()

            self._generate_mca_params(config, new_config_dir)
            for c in containers:
                config_files = new_config_dir + '/*'
                config_dirs.append([c['container'],
                                    config_files, 
                                    config.config_directory])
        return config_dirs, entry_point

class MPIConfig(object):
    log_directory = '/service/logs'
    config_directory = '/usr/local/etc/'

    BTL_PORT_MIN = 2000
    OOB_PORT_MIN = 6000
    PORT_RANGE = 4

    def __init__(self, num):
        self.num = num
        self.btl_port_min = 0
        self.btl_port_range = 0
        self.oob_port_min = 0
        self.oob_port_range = 0
        self.config_directory = MPIConfig.config_directory
        self.log_directory = MPIConfig.log_directory
